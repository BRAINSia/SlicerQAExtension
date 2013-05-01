#!/usr/bin/env python
import os
import warnings

from . import pg8000, sql


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
        >>> db1 = postgresDatabase('my.test.host', 0, 'myuser', 'MyDB', 'pass', 'login', 15)
        >>> db != None and db1 != None
        True
        >>> db.host == 'my.test.host' and db.port == 0 and db.pguser == 'myuser' and db.database == 'myuser' and db.pguser == db.database and db.password == 'pass' and db.login == 'login' and db.arraySize == 15
        True
        >>> db1.database == 'MyDB'
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
        self.rows = None
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
        self.arraySize = 1
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
        if self.database is None: self.database = self.pguser

    def openDatabase(self):
        """ Open the database and create cursor and connection
        >>> db = postgresDatabase()
        >>> db.openDatabase()
        >>> import pg8000 as pg
        >>> isinstance(db.connection, pg.DBAPI.ConnectionWrapper)
        True
        >>> isinstance(db.cursor, pg.DBAPI.CursorWrapper)
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
        >>> db = postgresDatabase(host='psych-db.psychiatry.uiowa.edu', pguser='test', database='test', password='test', login='user1')
        >>> db.getReviewerID(); db.reviewer_id == 1;
        True
        >>> db = postgresDatabase(host='psych-db.psychiatry.uiowa.edu', pguser='test', database='test', password='test', login='user0')
        >>> db.getReviewerID()
        Traceback (most recent call last):
            ...
        DataError: Reviewer user0 is not registered in the database test!
        """
        self.openDatabase()
        self.cursor.execute("SELECT reviewer_id FROM reviewers \
                             WHERE login=?", (self.login,))
        try:
            self.reviewer_id = self.cursor.fetchone()[0]
        except TypeError:
            raise pg8000.errors.DataError("Reviewer %s is not registered in the database %s!" % (self.login, self.database))
        finally:
            self.closeDatabase()

    def getBatch(self):
        """ Return a dictionary of rows where the number of rows == self.arraySize and status == 'U'
        ----------------------
        >>> db = postgresDatabase(host='psych-db.psychiatry.uiowa.edu', pguser='test', database='test', password='test', login='user1')
        >>> db.getBatch()
        Traceback (most recent call last):
            ...
        AttributeError: 'NoneType' object has no attribute 'execute'
        >>> db.openDatabase(); db.getBatch(); db.closeDatabase()
        >>> db.rows is None
        False
        >>> print "This testing is not complete!"
        """
        self.cursor.execute("SELECT * \
                            FROM dwi_raw \
                            WHERE status = 'U' \
                            ORDER BY priority")
        self.rows = self.cursor.fetchmany()
        if not self.rows:
            raise pg8000.errors.DataError("No rows were status == 'U' were found!")

    def lockBatch(self):
        """ Set the status of all batch members to 'L'
        ----------------------
        >>> db = postgresDatabase(host='psych-db.psychiatry.uiowa.edu', pguser='test', database='test', password='test', login='user1')
        >>> print "This testing is not complete!" # >>> db.openDatabase(); db.getBatch(); db.lockBatch() # >>> connection = pg8000...
        """
        ids = ()
        idString = ""
        for row in self.rows:
            record_id = row[0]
            ids = ids + (record_id,)
        idString = ("?, " * self.arraySize)[:-2]
        sqlCommand = "UPDATE dwi_raw \
                      SET status='L' \
                      WHERE record_id IN ({0})".format(idString)
        self.cursor.execute(sqlCommand, ids)
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
        return self.rows

    def writeReview(self, values):
        """ Write the review values to the postgres database

        Arguments:
        - `values`:
        """
        self.getReviewerID()
        self.openDatabase()
        try:
            valueString = ("?, " * (len(values) + 1))[:-2]
            sqlCommand = "INSERT INTO dwi_raw_reviews \
                            (record_id, \
                            question_one, question_two, question_three, question_four, \
                            reviewer_id\
                            ) VALUES (%s)" % valueString
            self.cursor.execute(sqlCommand, values + (self.reviewer_id,))
            self.connection.commit()
        except:
            print "Values attempted to write:", values, self.reviewer_id
            print "SQL COMMAND:", sqlCommand
            raise
        finally:
            self.closeDatabase()

    def unlockRecord(self, status='U', pKey=None):
        """ Unlock the record in dwi_raw by setting the status, dependent of the index value

        Arguments:
        - `pKey`: The value for the record_id column in the self.rows variable.
                  If pKey > -1, set that record's flag to 'R'.
                  If pKey is None, then set the remaining, unreviewed rows to 'U'
        """
        self.openDatabase()
        try:
            if not pKey is None:
                self.cursor.execute("UPDATE dwi_raw SET status=? \
                                     WHERE record_id=? AND status='L'", (status, pKey))
                self.connection.commit()
            else:
                for row in self.rows:
                    self.cursor.execute("SELECT status FROM dwi_raw WHERE record_id=?", (int(row[0]),))
                    currentStatus = self.cursor.fetchone()
                    if currentStatus[0] == 'L':
                        self.cursor.execute("UPDATE dwi_raw SET status='U' \
                                             WHERE record_id=? AND status='L'", (int(row[0]),))
                        self.connection.commit()
        except:
            raise
        finally:
            self.closeDatabase()

if __name__ == "__main__":
    import doctest
    import pg8000
    doctest.testmod()
