import os

try:
    from __main__ import ctk
    from __main__ import qt
    from __main__ import slicer
    from __main__ import vtk
except:
    pass

from . import __slicer_module__, postgresDatabase, dwiReader

try:
    import ConfigParser as cParser
    # import logging
    # import logging.handlers
except ImportError:
    print "External modules not found!"
    raise ImportError


class DWIRawQALogic(object):
    """ Logic class to be used 'under the hood' of the evaluator """
    def __init__(self, widget, test=False):
        self.widget = widget
        self.questions = self.widget.htmlFileName
        self.qaValueMap = {'yes':'1', 'no':'0'}
        self.user_id = None
        self.database = None
        self.batchSize = 1
        self.batchRows = None
        self.count = 0 # Starting value
        self.maxCount = 0
        self.currentSession = None
        self.currentFile = None
        self.currentValues = (None,)*len(self.questions)
        self.sessionFile = {}
        self.testing = test
        self.setup()

    def setup(self):
        """ Setup module logic

        >>> class widget(object):
        ...   def __init__(self, input):
        ...     self.images = (input,)
        ...

        >>> widget = widget('DWI')
        >>> logic = DWIPreprocessingQALogic(widget, True)
        >>> logic.database.database == 'test' and logic.database.host == 'psych-db.psychiatry.uiowa.edu' and logic.database.password == 'test' and logic.database.login == 'user1' and logic.database.pguser == 'test'
        True
        """
        config = cParser.SafeConfigParser()
        if self.testing:
            self.user_id = 'testuser1'
        else:
            self.user_id = os.environ['USER']
        configFile = os.path.join(__slicer_module__, 'autoworkup.cfg')
        if not os.path.exists(configFile):
            raise IOError("File {0} not found!".format(configFile))
        config.read(configFile)
        host = config.get('Postgres', 'Host')
        port = config.getint('Postgres', 'Port')
        database = config.get('Postgres', 'Database')
        db_user = config.get('Postgres', 'User')
        password = config.get('Postgres', 'Password') ### TODO: Use secure password handling (see RunSynchronization.py in phdxnat project)
        self.database = postgresDatabase(host, port, db_user, database, password,
                                         self.user_id, self.batchSize)

    def selectRegion(self, buttonName):
        """ Load the raw DWI image
        """
        nodeName = self.constructLabelNodeName(buttonName)
        dwiNode = slicer.util.getNode(nodeName)
        self.loadBackgroundNodeToMRMLScene(dwiNode)

    def constructLabelNodeName(self, buttonName):
        """ Create the names for the volume and label nodes """
        nodeName = '_'.join([self.currentSession, buttonName])
        return nodeName

    def onCancelButtonClicked(self):
        # TODO: Populate this function
        #   onNextButtonClicked WITHOUT the write to database
        print "Cancelled!"

    def writeToDatabase(self, evaluations):
        recordID = self.batchRows[self.count][0]
        values = (recordID,) + evaluations
        try:
            self.database.writeReview(values)
            self.database.unlockRecord('R', recordID)
        except:
            # TODO: Prompt user with popup
            print "Error writing to database!"
            raise

    def onGetBatchFilesClicked(self):
        """ """
        self.count = 0
        self.batchRows = self.database.lockAndReadRecords()
        self.maxCount = len(self.batchRows)
        self.constructFilePaths()
        self.setCurrentSession()
        self.loadData()
        gradientList = dwiReader(self.sessionFile['filePath'])
        self.widget.displayGradients(gradientList)

    def setCurrentSession(self):
        self.currentSession = self.sessionFile['session']
        self.widget.currentSession = self.currentSession

    def constructFilePaths(self):
        row = self.batchRows[self.count]
        self.sessionFile = {}
        baseDirectory = os.path.join(row[1], row[2], row[3], row[4], row[5])
        self.currentFile = row[6]
        fileName = '%s_%s_%s.nrrd' % (row[3], row[4], self.currentFile)
        self.sessionFile['file'] = fileName
        self.sessionFile['filePath'] = os.path.join(baseDirectory, fileName)
        self.sessionFile['session'] = row[4]
        self.sessionFile['record_id'] = row[0]
        # Verify that the files exist
        if not os.path.exists(self.sessionFile['filePath']):
            print "File not found: %s\nSkipping session..." % self.sessionFile['filePath']
            # raise IOError("File not found!\nFile: %s" % self.sessionFile[key])
            self.database.unlockRecord('M', self.sessionFile['record_id'])
            self.onGetBatchFilesClicked()
            # TODO: Generalize for a batch size > 1
            # for count in range(self.maxCount - self.count):
            #     print "This is the count: %d" % count

    def loadData(self):
        """ Load some default data for development and set up a viewing scenario for it.
        """
        dataDialog = qt.QPushButton();
        dataDialog.setText('Loading file for session %s...' % self.currentSession);
        dataDialog.show()
        volumeLogic = slicer.modules.volumes.logic()
        dwiNodeName = '%s_%s' % (self.currentSession, self.currentFile)
        dwiVolumeNode = slicer.util.getNode(dwiNodeName)
        if dwiVolumeNode is None:
            volumeLogic.AddArchetypeVolume(self.sessionFile['filePath'], dwiNodeName, 0)
            if slicer.util.getNode(dwiNodeName) is None:
                raise IOError("Could not load session file for DWI! File: %s" % self.sessionFile['DWI'])
            dwiVolumeNode = slicer.util.getNode(dwiNodeName)
            dwiVolumeNode.CreateDefaultDisplayNodes()
            dwiVolumeNode.GetDisplayNode().AutoWindowLevelOn()
        dataDialog.close()
        self.loadBackgroundNodeToMRMLScene(dwiVolumeNode)
        self.widget.dwiWidget.setMRMLVolumeNode(dwiVolumeNode)

    def loadBackgroundNodeToMRMLScene(self, volumeNode):
        # Set up template scene
        compositeNodes = slicer.util.getNodes('vtkMRMLSliceCompositeNode*')
        for compositeNode in compositeNodes.values():
            try:
                compositeNode.SetBackgroundVolumeID(volumeNode.GetID())
            except AttributeError:
                raise IOError("Could not find nodes for session %s" % self.currentSession)
        applicationLogic = slicer.app.applicationLogic()
        applicationLogic.FitSliceToAll()

    def getEvaluationValues(self):
        """ Get the evaluation values from the widget """
        values = ()
        for query in self.questions:
            yesButton, noButton = self.widget._findRadioButtons(query)
            if yesButton.isChecked():
                values = values + (self.qaValueMap['yes'],)
            elif noButton.isChecked():
                values = values + (self.qaValueMap['no'],)
            else:
                Exception('Session cannot be changed until all regions are evaluated.  Missing region: %s' % region)
        return values

    def onNextButtonClicked(self):
        """ Capture the evaluation values, write them to the database, reset the widgets, then load the next dataset """
        try:
            evaluations = self.getEvaluationValues()
        except:
            return
        # columns = ('record_id',)
        # for artifact in + self.widget.artifacts:
        #     for lobe in self.widget.lobes:
        #         columns = columns + ('%s_%s' % (artifact, lobe),)
        values = (self.sessionFile['record_id'], ) + evaluations
        ### HACK
        print values
        ###self.writeToDatabase(values)
        ### END ###
        count = self.count + 1
        if count <= self.maxCount - 1:
            self.count = count
        else:
            self.count = 0
        self.loadNewSession()
        self.widget.resetWidget()

    def onPreviousButtonClicked(self):
        try:
            evaluations = self.getEvaluationValues()
        except:
            return
        values = (self.sessionFile['record_id'], ) + evaluations
        ### HACK
        print values
        ### self.writeToDatabase(values)
        ### END ###
        count = self.count - 1
        if count >= 0:
            self.count = count
        else:
            self.count = self.maxCount - 1
        self.loadNewSession()
        self.widget.resetWidget()

    def loadNewSession(self):
        self.constructFilePaths()
        self.setCurrentSession()
        self.loadData()

    def exit(self):
        self.database.unlockRecord('U')

if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.NORMALIZE_WHITESPACE)
