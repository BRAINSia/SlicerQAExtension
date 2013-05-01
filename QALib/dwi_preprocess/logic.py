import os

try:
    from __main__ import ctk
    from __main__ import qt
    from __main__ import slicer
    from __main__ import vtk
except:
    pass

from . import __slicer_module__, postgresDatabase

try:
    import ConfigParser as cParser
    # import logging
    # import logging.handlers
except ImportError:
    print "External modules not found!"
    raise ImportError


class DWIPreprocessingQALogic(object):
    """ Logic class to be used 'under the hood' of the evaluator """
    def __init__(self, widget, test=False):
        self.widget = widget
        self.images = self.widget.images
        self.qaValueMap = {'good':'1', 'bad':'0', 'follow up':'-1'}
        self.colorTable = "IPL-BrainAtlas-ColorFile.txt"
        self.colorTableNode = None
        self.user_id = None
        self.database = None
        self.batchSize = 1
        self.batchRows = None
        self.count = 0 # Starting value
        self.maxCount = 0
        self.currentSession = None
        self.currentValues = (None,)*len(self.images)
        self.sessionFiles = {}
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
        # self.createColorTable()
        config = cParser.SafeConfigParser()
        if self.testing:
            configFile = os.path.join(__slicer_module__, 'test.cfg')
            self.user_id = 'user1'
        else:
            configFile = os.path.join(__slicer_module__, 'autoworkup.cfg')
            self.user_id = os.environ['USER']
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

    def createColorTable(self):
        """
        """
        self.colorTableNode = slicer.vtkMRMLColorTableNode()
        self.colorTableNode.SetFileName(os.path.join(__slicer_module__, 'Resources', 'ColorFile', self.colorTable))
        self.colorTableNode.SetName(self.colorTable[:-4])
        storage = self.colorTableNode.CreateDefaultStorageNode()
        slicer.mrmlScene.AddNode(storage)
        self.colorTableNode.AddAndObserveStorageNodeID(storage.GetID())
        slicer.mrmlScene.AddNode(self.colorTableNode)
        storage.SetFileName(self.colorTableNode.GetFileName())
        storage.SetReadState(True)
        storage.ReadData(self.colorTableNode, True)

    def addEntryToColorTable(self, buttonName):
        lTable = self.colorTableNode.GetLookupTable()
        colorIndex = self.colorTableNode.GetColorIndexByName(buttonName)
        color = lTable.GetTableValue(colorIndex)
        self.colorTableNode.AddColor(buttonName, *color)

    def selectRegion(self, buttonName):
        """ Load the outline of the selected region into the scene
        """
        nodeName = self.constructLabelNodeName(buttonName)
        labelNode = slicer.util.getNode(nodeName)
        if labelNode.GetLabelMap():
            labelNode.GetDisplayNode().SetAndObserveColorNodeID(self.colorTableNode.GetID())
            compositeNodes = slicer.util.getNodes('vtkMRMLSliceCompositeNode*')
            for compositeNode in compositeNodes.values():
                compositeNode.SetLabelVolumeID(labelNode.GetID())
                compositeNode.SetLabelOpacity(1.0)
            # Set the label outline to ON
            sliceNodes = slicer.util.getNodes('vtkMRMLSliceNode*')
            for sliceNode in sliceNodes.values():
                sliceNode.UseLabelOutlineOn()
        else:
             self.loadBackgroundNodeToMRMLScene(labelNode)

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
            print "Error writing to database! "
            print values
            raise

    def _getLabelFileNameFromRegion(self, regionName):
        try:
            region, side = regionName.split('_')
            fileName = '_'.join([side[0], region.capitalize(), 'seg.nii.gz'])
        except ValueError:
            region = regionName
            fileName = '_'.join([region, 'seg.nii.gz'])
        return fileName

    def onGetBatchFilesClicked(self):
        """ """
        self.count = 0
        self.batchRows = self.database.lockAndReadRecords()
        self.maxCount = len(self.batchRows)
        self.constructFilePaths()
        self.setCurrentSession()
        self.loadData()

    def setCurrentSession(self):
        self.currentSession = self.sessionFiles['session']
        self.widget.currentSession = self.currentSession

    def constructFilePaths(self):
        row = self.batchRows[self.count]
        sessionFiles = {}
        # Due to a poor choice in our database creation, the 'location' column is the 6th, NOT the 2nd
        baseDirectory = os.path.join(row[5], row[1], row[2], row[3], row[4])
        sessionFiles['session'] = row[4]
        sessionFiles['record_id'] = row[0]
        #outputDir = os.path.join(baseDirectory, 'DTIPrepOutput')
        outputDir = os.path.join(baseDirectory, '')
        outputList = os.listdir(outputDir)
        for item in outputList:
            if item.rfind('_QCed.nrrd') >= 0:
                sessionFiles['DWI'] = os.path.join(outputDir, item)
                break
        if not 'DWI' in sessionFiles.keys():
            raise IOError("File ending in _QCed.nrrd could not be found in directory %s" % outputDir)
        self.sessionFiles = sessionFiles
        # Verify that the files exist
        for key in self.images:
            if not os.path.exists(self.sessionFiles[key]):
                print "File not found: %s\nSkipping session..." % self.sessionFiles[key]
                self.database.unlockRecord('M', self.sessionFiles['record_id'])
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
        dwiNodeName = '%s_dwi' % self.currentSession
        dwiVolumeNode = slicer.util.getNode(dwiNodeName)
        if dwiVolumeNode is None:
            volumeLogic.AddArchetypeVolume(self.sessionFiles['DWI'], dwiNodeName, 0)
            if slicer.util.getNode(dwiNodeName) is None:
                raise IOError("Could not load session file for DWI! File: %s" % self.sessionFiles['DWI'])
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

    def loadNewSession(self):
        self.constructFilePaths()
        self.setCurrentSession()
        self.loadData()

    def exit(self):
        self.database.unlockRecord('U')

if __name__ == "__main__":
    import doctest
    doctest.testmod(optionflags=doctest.NORMALIZE_WHITESPACE)
