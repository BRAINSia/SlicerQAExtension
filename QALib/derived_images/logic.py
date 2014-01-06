try:
    import os
    import ConfigParser as cParser
    from . import __slicer_module__, postgresDatabase

    from __main__ import ctk
    from __main__ import qt
    from __main__ import slicer
    from __main__ import vtk
    # import logging
    # import logging.handlers
except ImportError:
    print "External modules not found!"
    # raise ImportError


class DerivedImageQALogic(object):
    """ Logic class to be used 'under the hood' of the evaluator """
    def __init__(self, widget, test=False):
        self.widget = widget
        self.regions = self.widget.regions
        self.images = self.widget.images
        self.qaValueMap = {'good':'1', 'bad':'0', 'follow up':'-1'}
        self.colorTable = "IPL-BrainAtlas-ColorFile.txt"
        self.colorTableNode = None
        self.user_id = None
        self.database = None
        self.config = None
        self.batchSize = 1
        self.batchRows = None
        self.count = 0 # Starting value
        self.maxCount = 0
        self.currentSession = None
        self.currentValues = (None,) * len(self.images + self.regions)
        self.sessionFiles = {}
        self.testing = test
        if self.testing:
            print "Testing logic is ON"
        self.setup()

    def setup(self):
        print "setup()"
        self.createColorTable()
        config = cParser.SafeConfigParser()
        self.config = cParser.SafeConfigParser()
        logicConfig = os.path.join(__slicer_module__, 'derived_images-all_Labels_seg.cfg')
        if self.testing:
            ### HACK
            databaseConfig = os.path.join(__slicer_module__, 'database.cfg.EXAMPLE')
            self.user_id = 'user1'
            ### END HACK
        else:
            databaseConfig = os.path.join(__slicer_module__, 'autoworkup.cfg')
            self.user_id = os.environ['USER']
        for configFile in [databaseConfig, logicConfig]:
            if not os.path.exists(configFile):
                raise IOError("File {0} not found!".format(configFile))
        config.read(databaseConfig)
        host = config.get('Postgres', 'Host')
        port = config.getint('Postgres', 'Port')
        database = config.get('Postgres', 'Database')
        db_user = config.get('Postgres', 'User')
        password = config.get('Postgres', 'Password') ### TODO: Use secure password handling (see RunSynchronization.py in phdxnat project)
        #        import hashlib as md5
        #        md5Password = md5.new(password)
        ### HACK
        if not self.testing:
            self.database = postgresDatabase(host, port, db_user, database, password,
                                             self.user_id, self.batchSize)
        ### END HACK
        self.config.read(logicConfig)


    def createColorTable(self):
        """
        """
        print "createColorTable()"
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
        print "addEntryToColorTable()"
        lTable = self.colorTableNode.GetLookupTable()
        colorIndex = self.colorTableNode.GetColorIndexByName(buttonName)
        color = lTable.GetTableValue(colorIndex)
        self.colorTableNode.AddColor(buttonName, *color)

    def selectRegion(self, buttonName):
        """ Load the outline of the selected region into the scene
        """
        print "selectRegion()"
        nodeName = self.constructLabelNodeName(buttonName)
        if nodeName == '':
            return -1
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
        print "constructLabelNodeName()"
        if not self.currentSession is None:
            nodeName = '_'.join([self.currentSession, buttonName])
            return nodeName
        return ''

    def onCancelButtonClicked(self):
        # TODO: Populate this function
        #   onNextButtonClicked WITHOUT the write to database
        print "Cancelled!"

    def writeToDatabase(self, evaluations):
        print "writeToDatabase()"
        if self.testing:
            recordID = str(self.batchRows[self.count]['record_id'])
        else:
            recordID = self.batchRows[self.count][0]
        values = (recordID,) + evaluations
        try:
            if self.testing:
                self.database.writeAndUnlockRecord(values)
            else:
                self.database.writeReview(values)
                self.database.unlockRecord('R', recordID)
        except:
            # TODO: Prompt user with popup
            print "Error writing to database!"
            raise

    def _getLabelFileNameFromRegion(self, regionName):
        print "_getLabelFileNameFromRegion()"
        try:
            region, side = regionName.split('_')
            fileName = '_'.join([side[0], region.capitalize(), 'seg.nii.gz'])
        except ValueError:
            region = regionName
            fileName = '_'.join([region, 'seg.nii.gz'])
        return fileName

    def onGetBatchFilesClicked(self):
        """ """
        print "onGetBatchFilesClicked()"
        self.count = 0
        self.batchRows = self.database.lockAndReadRecords()
        self.maxCount = len(self.batchRows)
        self.constructFilePaths()
        self.setCurrentSession()
        self.loadData()


    def setCurrentSession(self):
        print "setCurrentSession()"
        self.currentSession = self.sessionFiles['session']
        self.widget.currentSession = self.currentSession


    def _all_Labels_seg(self, oldfilename, nodeName, level, session):
        """
        From PREDICTIMG-2335: Derived Images QA has been loading the individual segmentations in the
        CleanedDenoisedRFSegmentations folder, not the combined all_Labels_seg file which has the final segmentations after
        competition.  Load the correct labels from all_Labels_seg.nii.gz and have the corresponding labels display for each label
        choice in the module.
        """
        import numpy
        allLabelName = 'allLabels_seg_{0}'.format(session)
        labelNode = slicer.util.getNode(allLabelName)
        if labelNode is None:
            isLoaded, labelNode = slicer.util.loadLabelVolume(oldfilename, properties={'labelmap': True}, returnNode=True)
            labelNode.SetName(allLabelName)
            assert isLoaded, "Segmentation label file {0} could not be loaded".format(oldfilename)
        la = slicer.util.array(labelNode.GetID())
        outputLabelNode = slicer.modules.volumes.logic().CloneVolume(slicer.mrmlScene, labelNode, nodeName)
        ma = slicer.util.array(outputLabelNode.GetID())
        mask = numpy.ndarray.copy(la)
        mask[mask != level] = 0
        mask[mask == level] = 1
        ma[:] = mask
        outputLabelNode.GetImageData().Modified()


    def constructFilePaths(self):
        """
        >>> import DerivedImagesQA as diqa
        External modules not found!
        /Volumes/scratch/welchdm/src/Slicer-extensions/SlicerQAExtension
        External modules not found!
        >>> test = diqa.DerivedImageQAWidget(None, True)
        Testing logic is ON
        >>> test.logic.count = 0 ### HACK
        >>> test.logic.batchRows = [['rid','exp', 'site', 'sbj', 'ses', 'loc']] ### HACK
        >>> test.logic.constructFilePaths()
        Test: loc/exp/site/sbj/ses/TissueClassify/t1_average_BRAINSABC.nii.gz
        File not found for file: t2_average
        Skipping session...
        Test: loc/exp/site/sbj/ses/TissueClassify/t1_average_BRAINSABC.nii.gz
        File not found for file: t1_average
        Skipping session...
        Test: loc/exp/site/sbj/ses/TissueClassify/fixed_brainlabels_seg.nii.gz
        File not found for file: labels_tissue
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/l_caudate_seg.nii.gz
        File not found for file: caudate_left
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/r_caudate_seg.nii.gz
        File not found for file: caudate_right
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/l_accumben_seg.nii.gz
        File not found for file: accumben_left
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/r_accumben_seg.nii.gz
        File not found for file: accumben_right
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/l_putamen_seg.nii.gz
        File not found for file: putamen_left
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/r_putamen_seg.nii.gz
        File not found for file: putamen_right
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/l_globus_seg.nii.gz
        File not found for file: globus_left
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/r_globus_seg.nii.gz
        File not found for file: globus_right
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/l_thalamus_seg.nii.gz
        File not found for file: thalamus_left
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/r_thalamus_seg.nii.gz
        File not found for file: thalamus_right
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/l_hippocampus_seg.nii.gz
        File not found for file: hippocampus_left
        Skipping session...
        Test: loc/exp/site/sbj/ses/DenoisedRFSegmentations/r_hippocampus_seg.nii.gz
        File not found for file: hippocampus_right
        Skipping session...
        """
        print "constructFilePaths()"
        row = self.batchRows[self.count]
        sessionFiles = {}
        # Due to a poor choice in our database creation, the 'location' column is the 6th, NOT the 2nd
        baseDirectory = os.path.join(row[5], row[1], row[2], row[3], row[4])
        sessionFiles['session'] = row[4]
        sessionFiles['record_id'] = row[0]

        for image in self.images + self.regions:
            sessionFiles[image] = None
            imageDirs = eval(self.config.get(image, 'directories'))
            imageFiles = eval(self.config.get(image, 'filenames'))
            for _dir in imageDirs:
                for _file in imageFiles:
                    temp = os.path.join(baseDirectory, _dir, _file)
                    if os.path.exists(temp):
                        sessionFiles[image] = temp
                        if self.config.has_option(image, 'label'):  # uses all_Labels_seg.nii.gz
                            assert image in self.regions, "{0} is NOT a region".format(image)
                            imageThreshold = eval(self.config.get(image, 'label'))  # Threshold value for all_Labels_seg.nii.gz
                            regionNodeName = "%s_%s" %(sessionFiles['session'], image)
                            self._all_Labels_seg(temp, nodeName=regionNodeName, level=imageThreshold,
                                                 session=sessionFiles['session'])  # Create nodes in mrmlScene
                        break ; break
                    elif self.testing:
                        print "Test: %s" % temp
                    elif image == 't2_average':
                        # Assume this is a T1-only session
                        sessionFiles[image] = os.path.join(__slicer_module__, 'Resources', 'images', 'emptyImage.nii.gz')
                        break; break;
                    else:
                        print "File not found: %s" % temp
            if sessionFiles[image] is None:
                print "Skipping session %s..." % sessionFiles['session']
                # raise IOError("File not found!\nFile: %s" % sessionFiles[image])
                if not self.testing:
                    self.database.unlockRecord('M', sessionFiles['record_id'])
                    print "*" * 50
                    print "DEBUG: sessionFiles ", sessionFiles
                    print "DEBUG: image ", image
                break
        if None in sessionFiles.values():
            print "DEBUG: calling onGetBatchFilesClicked()..."
            self.onGetBatchFilesClicked()
            # TODO: Generalize for a batch size > 1
            # for count in range(self.maxCount - self.count):
            #     print "This is the count: %d" % count
        else:
            self.sessionFiles = sessionFiles


    def loadData(self):
        """ Load some default data for development and set up a viewing scenario for it.
        """
        print "loadData()"
        dataDialog = qt.QPushButton();
        dataDialog.setText('Loading files for session %s...' % self.currentSession);
        dataDialog.show()
        volumeLogic = slicer.modules.volumes.logic()
        t1NodeName = '%s_t1_average' % self.currentSession
        t1VolumeNode = slicer.util.getNode(t1NodeName)
        if t1VolumeNode is None:
            try:
                volumeLogic.AddArchetypeScalarVolume(self.sessionFiles['t1_average'], t1NodeName, 0, None)
            except TypeError:
                print "DEBUG: ", self.sessionFiles['t1_average']
                volumeLogic.AddArchetypeScalarVolume(self.sessionFiles['t1_average'], t1NodeName, 0)
                print "DEBUG: done"
            if slicer.util.getNode(t1NodeName) is None:
                raise IOError("Could not load session file for T1! File: %s" % self.sessionFiles['t1_average'])
            t1VolumeNode = slicer.util.getNode(t1NodeName)
            t1VolumeNode.CreateDefaultDisplayNodes()
            t1VolumeNode.GetDisplayNode().AutoWindowLevelOn()
        t2NodeName = '%s_t2_average' % self.currentSession
        t2VolumeNode = slicer.util.getNode(t2NodeName)
        if t2VolumeNode is None:
            try:
                volumeLogic.AddArchetypeScalarVolume(self.sessionFiles['t2_average'], t2NodeName, 0, None)
            except TypeError:
                print "DEBUG: ", self.sessionFiles['t2_average']
                volumeLogic.AddArchetypeScalarVolume(self.sessionFiles['t2_average'], t2NodeName, 0)
                print "DEBUG: done"
            if slicer.util.getNode(t2NodeName) is None:
                raise IOError("Could not load session file for T2! File: %s" % self.sessionFiles['t2_average'])
            t2VolumeNode = slicer.util.getNode(t2NodeName)
            t2VolumeNode.CreateDefaultDisplayNodes()
            t2VolumeNode.GetDisplayNode().AutoWindowLevelOn()
        for region in self.regions:
            regionNodeName = '%s_%s' % (self.currentSession, region)
            regionNode = slicer.util.getNode(regionNodeName)
            if regionNode is None:
                try:
                    volumeLogic.AddArchetypeScalarVolume(self.sessionFiles[region], regionNodeName, 1, None)
                except TypeError:
                    print "DEBUG: ", self.sessionFiles[region]
                    volumeLogic.AddArchetypeScalarVolume(self.sessionFiles[region], regionNodeName, 1)
                    print "DEBUG: done"
                if slicer.util.getNode(regionNodeName) is None:
                    raise IOError("Could not load session file for region %s! File: %s" % (region, self.sessionFiles[region]))
                regionNode = slicer.util.getNode(regionNodeName)
                displayNode = slicer.vtkMRMLLabelMapVolumeDisplayNode()
                slicer.mrmlScene.AddNode(displayNode)
                regionNode.SetAndObserveNthDisplayNodeID(0, displayNode.GetID())
        dataDialog.close()

    def loadBackgroundNodeToMRMLScene(self, volumeNode):
        # Set up template scene
        print "loadBackgroundNodeToMRMLScene()"
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
        print "getEvaluationValues()"
        values = ()
        for region in self.regions:
            goodButton, badButton = self.widget._findRadioButtons(region)
            if goodButton.isChecked():
                values = values + (self.qaValueMap['good'],)
            elif badButton.isChecked():
                values = values + (self.qaValueMap['bad'],)
            else:
                Exception('Session cannot be changed until all regions are evaluated.  Missing region: %s' % region)
        return values

    def onNextButtonClicked(self):
        """ Capture the evaluation values, write them to the database, reset the widgets, then load the next dataset """
        print "onNextButtonClicked()"
        try:
            evaluations = self.getEvaluationValues()
        except:
            return
        columns = ('record_id',) + self.regions
        values = (self.sessionFiles['record_id'], ) + evaluations
        try:
            self.writeToDatabase(values)
        except sqlite3.OperationalError:
            print "Error here"
        count = self.count + 1
        if count <= self.maxCount - 1:
            self.count = count
        else:
            self.count = 0
        self.loadNewSession()
        self.widget.resetWidget()

    def onPreviousButtonClicked(self):
        print "onPreviousButtonClicked()"
        try:
            evaluations = self.getEvaluationValues()
        except:
            return
        columns = ('record_id', ) + self.regions
        values = (self.sessionFiles['record_id'], ) + evaluations
        self.writeToDatabase(values)
        count = self.count - 1
        if count >= 0:
            self.count = count
        else:
            self.count = self.maxCount - 1
        self.loadNewSession()
        self.widget.resetWidget()

    def loadNewSession(self):
        print "loadNewSession()"
        self.constructFilePaths()
        self.setCurrentSession()
        self.loadData()

    def exit(self):
        print "exit()"
        self.database.unlockRecord('U')

# if __name__ == '__main__':
#     import doctest
#     doctest.testmod()
