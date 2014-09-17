#!/usr/bin/env python
from collections import deque
import os
import warnings

from . import pg8000, sql

SCHEMA='autoworkup_scm'

class postgresDatabase(object):
    """ Connect to the Postgres database and prevent multiple user collisions
        during simultaneous evaluations
    """

    def __init__(self, *args, **kwds):
        """ Set the class attributes needed for connecting to the database and interacting with it
        ------------------------
        Arguments:
        - `host`: The name of the host machine (default = 'localhost')
        - `port`: The port number (default = 5432)
        - `pguser`: The username to connect to the Postgres server with, default is 'postgres'
        - `database`: The name of the database to connect to.  If omitted, it is the same as the `user`
        - `password`: The password associated with the `user` on the Postgres server, default is 'postgres'
        - `login`: The reviewer login ID, normally $USER
        - `arraySize`: The number of rows to return
        ------------------------
        >>> import os
        >>> db = postgresDatabase()
        >>> db != None
        True
        >>> db.host == 'localhost' and db.port == 5432 and db.pguser == 'postgres' and db.pguser == db.database and db.pguser == db.password and db.login == os.environ['USER'] and db.arraySize == 1
        True
        >>> # Test positional args
        >>> db = postgresDatabase('my.test.host', 0, 'myuser', None, 'pass', 'login', 15)
        >>> db != None
        True
        >>> db.host == 'my.test.host' and db.port == 0 and db.pguser == 'myuser' and db.pguser == db.database and db.password == 'pass' and db.login == 'login' and db.arraySize == 15
        True
        >>> # Test a mix
        >>> db = postgresDatabase('my.test.host', 'myuser', port=15, database='postgres', arraySize=15, password='pass', pguser='login')
        >>> db != None
        True
        >>> db.host == 'my.test.host' and db.port == 15 and db.pguser == 'login' and db.database == 'postgres' and db.password == 'pass' and db.login == 'myuser' and db.arraySize == 15
        True
        >>> # Test keyword args
        >>> db = postgresDatabase(host='my.test.host', arraySize=15, login='myuser', password='pass', database=None, pguser='login', port=15)
        >>> db != None
        True
        >>> db.host == 'my.test.host' and db.port == 15 and db.pguser == 'login' and db.pguser == db.database and db.password == 'pass' and db.login == 'myuser' and db.arraySize == 15
        True
        """
        sql.paramstyle = "qmark"
        self.row = None
        self.connection = None
        self.cursor = None
        # self.isolationLevel = sql.extensions.ISOLATION_LEVEL_SERIALIZABLE
        # Set defaults
        self.host = 'localhost'
        self.port = 5432
        self.pguser = 'postgres'
        self.database = None
        self.password = 'postgres'
        self.login = os.environ['USER']
        # Set keyword inputs
        if not kwds is None:
            argkeys = ['host', 'port', 'pguser', 'database', 'password', 'login', 'arraySize']
            keys = sorted(kwds.keys())
            for key in keys:
                argkeys.remove(key)
                value = kwds[key]
                setattr(self, key, value)
        if len(argkeys) == len(args) and len(args) > 0:
                for key, arg in zip(argkeys, args):
                    setattr(self, key, arg)
        # Set the database default
        if self.database is None:
            self.database = self.pguser
        self.review_column_names = self.review_columns()
        self.previous_status = 'E'


    def openDatabase(self):
        """ Open the database and create cursor and connection
        >>> db = postgresDatabase()
        >>> db.openDatabase()
        >>> import pg8000 as sql
        >>> isinstance(db.connection, sql.DBAPI.ConnectionWrapper)
        True
        >>> isinstance(db.cursor, sql.DBAPI.CursorWrapper)
        True
        """
        self.connection = sql.connect(host=self.host,
                                      port=self.port,
                                      database=self.database,
                                      user=self.pguser,
                                      password=self.password)
        self.cursor = self.connection.cursor()
        self.cursor.arraysize = self.arraySize

    def closeDatabase(self):
        """ Close cursor and connection, setting values to None
        """
        self.cursor.close()
        self.cursor = None
        self.connection.close()
        self.connection = None

    def getReviewerID(self):
        """ Using the database login name, get the reviewer_id key from the reviewers table
        ------------------------
        >>> db = postgresDatabase(host='opteron.psychiatry.uiowa.edu', pguser='tester', database='test', password='test1', login='user1')
        >>> db.getReviewerID(); db.reviewer_id == 1;
        True
        >>> db = postgresDatabase(host='opteron.psychiatry.uiowa.edu', pguser='tester', database='test', password='test1', login='user0')
        >>> db.getReviewerID();
        Traceback (most recent call last):
            ...
        DataError: Reviewer user0 is not registered in the database test!
        """
        self.openDatabase()
        self.cursor.execute("SELECT reviewer_id FROM {schema}.reviewers \
                             WHERE login=?".format(schema=SCHEMA), (self.login,))
        try:
            self.reviewer_id = self.cursor.fetchone()[0]
        except TypeError:
            raise pg8000.errors.DataError("Reviewer %s is not registered in the database %s!" % (self.login, self.database))
        finally:
            self.closeDatabase()

    def getBatch(self):
        """ Return a dictionary of rows where the number of rows == self.arraySize and status == 'U'
        ----------------------
        >>> db = postgresDatabase(host='opteron.psychiatry.uiowa.edu', pguser='tester', database='test', password='test1', login='user1')
        >>> db.getBatch()
        Traceback (most recent call last):
            ...
        AttributeError: 'NoneType' object has no attribute 'execute'
        >>> db.openDatabase(); db.getBatch(); db.closeDatabase()
        >>> self.row is None
        True
        """
        # HACK: priority = 1
        self.cursor.execute("SELECT * \
                             FROM {schema}.derived_images \
                             WHERE status IN ('U', 'A') AND priority=1 \
                             ORDER BY priority ASC, status ASC".format(schema=SCHEMA))
        # END HACK
        self.row = self.cursor.fetchone()
        if self.row is None:
            raise pg8000.errors.DataError("No rows with status 'U' or 'A' were found!")
        self.previous_state = self.row[-2]
        if self.previous_state != 'A':
            print "Not roboRated! ", self.row
        else:
            self.checkForRobotRating()

    def checkForRobotRating(self):
        roboraterID = 9  #TODO: HARDCODED, replace with query: SELECT reviewer_id FROM reviewers WHERE "login" = 'roborater'
        columns = ', '.join(self.review_column_names)
        # print self.row
        record_id = self.row[0]
        self.cursor.execute("SELECT {columns} FROM {schema}.image_reviews WHERE reviewer_id=? AND record_id=? ORDER BY review_time".format(schema=SCHEMA, columns=columns), (roboraterID, record_id))
        review = self.cursor.fetchone()
        assert review is not None and review is not [], "Cannot find automated QA for record!"
        print type(review)
        if isinstance(self.row, tuple):  # pg8000 v1.08
            self.row = self.row + review
        elif isinstance(self.row, deque):  # pg8000 v1.9+
            # print "The length of the row: ", len(self.row)
            temp = self.row.popleft()
            self.row.appendleft(temp + review)
        else:
            raise TypeError
        print self.row
        return

    def lockBatch(self):
        """ Set the status of all batch members to 'L'
        """
        record_id = self.row[0]
        sqlCommand = "UPDATE {schema}.derived_images \
                      SET status='L' \
                      WHERE record_id=?".format(schema=SCHEMA)
        self.cursor.execute(sqlCommand, (int(record_id), ))
        self.connection.commit()

    def lockAndReadRecords(self):
        """ Find a given number of records with status == 'U', set the status to 'L',
            and return the records in a dictionary-like object
        """
        self.openDatabase()
        try:
            self.getBatch()
            self.lockBatch()
        finally:
            self.closeDatabase()
        return [self.row]


    def writeReview(self, values):
        """ Write the review values to the postgres database

        Arguments:
        - `values`:
        """
        self.getReviewerID()
        self.openDatabase()
        try:
            valueString = ("?, " * (len(values) + 1))[:-2]
            sqlCommand = "INSERT INTO {schema}.image_reviews \
                            (record_id, t2_average, t1_average, \
                            labels_tissue, caudate_left, caudate_right, \
                            accumben_left, accumben_right, putamen_left, \
                            putamen_right, globus_left, globus_right, \
                            thalamus_left, thalamus_right, hippocampus_left, \
                            hippocampus_right, notes, reviewer_id\
                            ) VALUES".format(schema=SCHEMA) + " (%s)" % valueString
            self.cursor.execute(sqlCommand, values + (self.reviewer_id,))
            self.connection.commit()
        except:
            raise
        finally:
            self.closeDatabase()

    def unlockRecord(self, status='U', pKey='-1'):
        """ Unlock the record in {schema}.derived_images by setting the status, dependent of the index value

        Arguments:
        - `pKey`: The value for the record_id column in the self.row variable.
                  If pKey > -1, set that record's flag to 'R'.
                  If pKey is None, then set the remaining, unreviewed rows to 'U'
        """
        self.openDatabase()
        pKey = int(pKey)
        try:
            if pKey > 1:
                self.cursor.execute("UPDATE {schema}.derived_images SET status=? \
                                     WHERE record_id=? AND status='L'".format(schema=SCHEMA), (status, pKey))
            else:
                self.cursor.execute("SELECT status FROM {schema}.derived_images WHERE record_id=?".format(schema=SCHEMA),
                                    (int(self.row[0]),))
                currentStatus = self.cursor.fetchone()[0]
                if currentStatus == 'L':
                    self.cursor.execute("UPDATE {schema}.derived_images SET status=? \
                                         WHERE record_id=? AND status='L'".format(schema=SCHEMA),
                                         (self.previous_state, int(self.row[0]),))
                else:
                    self.unlockRecord(status='E', pKey=int(self.row[0]))
                    raise NotImplementedError
            self.connection.commit()
        except:
            raise
        finally:
            self.closeDatabase()

    def review_columns(self):
        tablename = 'image_reviews'
        self.openDatabase()
        try:
            self.cursor.execute("SELECT column_name FROM information_schema.columns \
                                 WHERE table_name=? ORDER BY ordinal_position", (tablename, ))
            columns = tuple([x[0] for x in self.cursor.fetchall()])
            assert columns[0] == 'review_id', "First column is not 'review_id'"
            assert columns[19] == 'notes', "Last column is not 'notes'"
        except:
            raise
        self.closeDatabase()
        return columns

if __name__ == "__main__":
    import doctest
    import pg8000
    doctest.testmod()
