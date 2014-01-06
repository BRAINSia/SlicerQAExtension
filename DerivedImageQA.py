#! /usr/bin/env python
### TODO: Add logging
try:
    import os
    from QALib.derived_images import *
    from QALib.derived_images import __slicer_module__
    print __slicer_module__
    from __main__ import ctk
    from __main__ import qt
    from __main__ import slicer
    from __main__ import vtk
#     import logging
#     import logging.handlers
except ImportError:
    print "External modules not found!"
#     raise ImportError

class DerivedImageQA:
    def __init__(self, parent):
        parent.title = 'Derived Images'
        parent.categories = ['Quality Assurance']
        parent.dependencies = ['Volumes']
        parent.contributors = ['Dave Welch (UIowa), Hans Johnson (UIowa)']
        parent.helpText = """Image evaluation module for use in the UIowa PINC lab"""
        parent.acknowledgementText = """ """
        self.parent = parent


class DerivedImageQAWidget:
    def __init__(self, parent=None, test=False):
        self.images = ('t2_average', 't1_average') # T1 is second so that reviewers see it as background for regions
        self.regions = ('labels_tissue',
                        'caudate_left', 'caudate_right',
                        'accumben_left', 'accumben_right',
                        'putamen_left', 'putamen_right',
                        'globus_left', 'globus_right',
                        'thalamus_left', 'thalamus_right',
                        'hippocampus_left', 'hippocampus_right')
        self.currentSession = None
        self.imageQAWidget = None
        self.navigationWidget = None
        self.followUpDialog = None
        self.notes = None
        # Handle the UI display with/without Slicer
        if parent is None and not test:
            self.parent = slicer.qMRMLWidget()
            self.parent.setLayout(qt.QVBoxLayout())
            self.parent.setMRMLScene(slicer.mrmlScene)
            self.layout = self.parent.layout()
            self.logic = DerivedImageQALogic(self)
            self.setup()
            self.parent.show()
        elif not test:
            self.parent = parent
            self.layout = self.parent.layout()
            self.logic = DerivedImageQALogic(self, test=test)
        elif test:
            self.logic = DerivedImageQALogic(self, test=test)

    def setup(self):
        self.followUpDialog = self.loadUIFile('Resources/UI/followUpDialog.ui')
        self.clipboard = qt.QApplication.clipboard()
        self.textEditor = self.followUpDialog.findChild("QTextEdit", "textEditor")
        buttonBox = self.followUpDialog.findChild("QDialogButtonBox", "buttonBox")
        buttonBox.connect("accepted()", self.grabNotes)
        buttonBox.connect("rejected()", self.cancelNotes)
        # Batch navigation
        self.navigationWidget = self.loadUIFile('Resources/UI/navigationCollapsibleButton.ui')
        nLayout = qt.QVBoxLayout(self.navigationWidget)
        # TODO: Fix batch list sizing
        ### nLayout.addWidget(self.navigationWidget.findChild("QLabel", "batchLabel"))
        ### nLayout.addWidget(self.navigationWidget.findChild("QListWidget", "batchList"))
        nLayout.addWidget(self.navigationWidget.findChild("QWidget", "buttonContainerWidget"))
        # Find navigation buttons
        self.previousButton = self.navigationWidget.findChild("QPushButton", "previousButton")
        self.quitButton = self.navigationWidget.findChild("QPushButton", "quitButton")
        self.nextButton = self.navigationWidget.findChild("QPushButton", "nextButton")
        self.connectSessionButtons()
        # Evaluation subsection
        self.imageQAWidget = self.loadUIFile('Resources/UI/imageQACollapsibleButton.ui')
        qaLayout = qt.QVBoxLayout(self.imageQAWidget)
        qaLayout.addWidget(self.imageQAWidget.findChild("QFrame", "titleFrame"))
        qaLayout.addWidget(self.imageQAWidget.findChild("QFrame", "tableVLine"))
        # Create review buttons on the fly
        for image in self.images + self.regions:
            reviewButton = self.reviewButtonFactory(image)
            qaLayout.addWidget(reviewButton)
        self.connectReviewButtons()
        # resetButton
        self.resetButton = qt.QPushButton()
        self.resetButton.setText('Reset evaluation')
        self.resetButton.connect('clicked(bool)', self.resetWidget)
        # batch button
        self.batchButton = qt.QPushButton()
        self.batchButton.setText('Get evaluation batch')
        self.batchButton.connect('clicked(bool)', self.onGetBatchFilesClicked)
        # Add all to layout
        self.layout.addWidget(self.navigationWidget)
        nLayout.addWidget(self.resetButton)
        nLayout.addWidget(self.batchButton)
        self.layout.addWidget(self.imageQAWidget)
        self.layout.addStretch(1)
        ### TESTING ###
        if True:
            print "Gui calling logic.onGetBatchFilesClicked()"
            self.logic.onGetBatchFilesClicked()
        ### END ###

    def loadUIFile(self, fileName):
        """ Return the object defined in the Qt Designer file """
        uiloader = qt.QUiLoader()
        qfile = qt.QFile(os.path.join(__slicer_module__, fileName))
        qfile.open(qt.QFile.ReadOnly)
        try:
            return uiloader.load(qfile)
        finally:
            qfile.close()

    def reviewButtonFactory(self, image):
        widget = self.loadUIFile('Resources/UI/reviewButtonsWidget.ui')
        # Set push button
        pushButton = widget.findChild("QPushButton", "imageButton")
        pushButton.objectName = image
        pushButton.setText(self._formatText(image))
        radioContainer = widget.findChild("QWidget", "radioWidget")
        radioContainer.objectName = image + "_radioWidget"
        # Set radio buttons
        goodButton = widget.findChild("QRadioButton", "goodButton")
        goodButton.objectName = image + "_good"
        badButton = widget.findChild("QRadioButton", "badButton")
        badButton.objectName = image + "_bad"
        followUpButton = widget.findChild("QRadioButton", "followUpButton")
        followUpButton.objectName = image + "_followUp"
        return widget

    def _formatText(self, text):
        parsed = text.split("_")
        if len(parsed) > 1:
            text = " ".join([parsed[1].capitalize(), parsed[0]])
        else:
            text = parsed[0].capitalize()
        return text

    def connectSessionButtons(self):
        """ Connect the session navigation buttons to their logic """
        # TODO: Connect buttons
        ### self.nextButton.connect('clicked()', self.logic.onNextButtonClicked)
        ### self.previousButton.connect('clicked()', self.logic.onPreviousButtonClicked)
        self.quitButton.connect('clicked()', self.exit)

    def connectReviewButtons(self):
        """ Map the region buttons clicked() signals to the function """
        self.buttonMapper = qt.QSignalMapper()
        self.buttonMapper.connect('mapped(const QString&)', self.logic.selectRegion)
        self.buttonMapper.connect('mapped(const QString&)', self.enableRadios)
        for image in self.images + self.regions:
            pushButton = self.imageQAWidget.findChild('QPushButton', image)
            self.buttonMapper.setMapping(pushButton, image)
            pushButton.connect('clicked()', self.buttonMapper, 'map()')

    def enableRadios(self, image):
        """ Enable the radio buttons that match the given region name """
        self.imageQAWidget.findChild("QWidget", image + "_radioWidget").setEnabled(True)
        for suffix in ("_good", "_bad", "_followUp"):
            radio = self.imageQAWidget.findChild("QRadioButton", image + suffix)
            radio.setShortcutEnabled(True)
            radio.setCheckable(True)
            radio.setEnabled(True)

    def disableRadios(self, image):
        """ Disable all radio buttons that DO NOT match the given region name """
        radios = self.imageQAWidget.findChildren("QRadioButton")
        for radio in radios:
            if radio.objectName.find(image) == -1:
                radio.setShortcutEnabled(False)
                radio.setEnabled(False)

    def resetRadioWidgets(self):
        """ Disable and reset all radio buttons in the widget """
        radios = self.imageQAWidget.findChildren("QRadioButton")
        for radio in radios:
            radio.setCheckable(False)
            radio.setEnabled(False)

    def getRadioValues(self):
        values = ()
        needsFollowUp = False
        radios = self.imageQAWidget.findChildren("QRadioButton")
        for image in self.images + self.regions:
            for radio in radios:
                if radio.objectName.find(image) > -1 and radio.checked:
                    if radio.objectName.find("_good") > -1:
                        values = values + (1,)
                    elif radio.objectName.find("_bad") > -1:
                        values = values + (0,)
                    elif radio.objectName.find("_followUp") > -1:
                        values = values + (-1,)
                        needsFollowUp = True
                    else:
                        values = values + ("NULL",)
                        print "Warning: No value for %s" % image
        if needsFollowUp:
            self.followUpDialog.exec_()
            if self.followUpDialog.result() and not self.notes is None:
                values = values + (self.notes,)
            else:
                values = values + ("NULL",)
        else:
            values = values + ("NULL",)
        return values

    def resetWidget(self):
        self.resetRadioWidgets()
        self.resetClipboard()

    def grabNotes(self):
        self.notes = None
        self.notes = str(self.textEditor.toPlainText())
        # TODO: Format notes
        ### if self.notes = '':
        ###     self.followUpDialog.show()
        ###     self.textEditor.setText("A comment is required!")
        self.textEditor.clear()

    def cancelNotes(self):
        # TODO:
        pass

    def resetClipboard(self):
        self.clipboard.clear()

    def onGetBatchFilesClicked(self):
        print "gui:onGetBatchFilesClicked()"
        values = self.getRadioValues()
        if len(values) >= len(self.images + self.regions):
            self.logic.writeToDatabase(values)
            self.resetWidget()
            self.logic.onGetBatchFilesClicked()
        else:
            # TODO: Handle this case intelligently
            print "Not enough values for the required columns!"


    def exit(self):
        """ When Slicer exits, prompt user if they want to write the last evaluation """
        values = self.getRadioValues()
        if len(values) >= len(self.images + self.regions):
            # TODO: Write a confirmation dialog popup
            self.logic.writeToDatabase(values)
        elif len(values) == 0:
            self.logic.exit()
        else:
            # TODO: write a prompt window
            print "Not enough values for the required columns!"
            self.logic.exit()
            # TODO: clear scene
