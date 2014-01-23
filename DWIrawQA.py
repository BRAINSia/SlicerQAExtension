#! /usr/bin/env python
import os
import re

from __main__ import ctk
from __main__ import qt
from __main__ import slicer
from __main__ import vtk

from QALib.dwi_raw import *
from QALib.dwi_raw import __slicer_module__

### TODO: Add logging
# try:
#     import logging
#     import logging.handlers
# except ImportError:
#     print "External modules not found!"
#     raise ImportError

class DWIrawQA:
    def __init__(self, parent):
        parent.title = 'DWI Raw Inspection'
        parent.categories = ['Quality Assurance']
        parent.dependencies = ['Volumes']
        parent.contributors = ['Dave Welch (UIowa)']
        parent.helpText = """DWI raw image evaluation module for use in the UIowa PINC lab"""
        parent.acknowledgementText = """ """
        self.parent = parent


class DWIrawQAWidget:
    def __init__(self, parent=None):
        self.htmlFileName = ('dwi_raw_1', 'dwi_raw_2',
                             'dwi_raw_3', 'dwi_raw_4')
        self.css = None
        self.currentSession = None
        self.navigationWidget = None
        self.gradientDisplayWidget = None
        self.followUpDialog = None
        self.notes = None
        # Handle the UI display with/without Slicer
        if parent is None:
            self.parent = slicer.qMRMLWidget()
            self.parent.setLayout(qt.QVBoxLayout())
            self.parent.setMRMLScene(slicer.mrmlScene)
            self.layout = self.parent.layout()
            self.logic = DWIRawQALogic(self, False)
            self.setup()
            self.parent.show()
        else:
            self.parent = parent
            self.layout = self.parent.layout()
            self.logic = DWIRawQALogic(self, False)

    def setup(self):
        self.followUpDialog = self.loadUIFile('Resources/UI/notesDialog.ui')
        self.clipboard = qt.QApplication.clipboard()
        self.textEditor = self.followUpDialog.findChild("QTextEdit", "textEditor")
        self.textEditor.connect("clear()", self.resetClipboard)
        buttonBox = self.followUpDialog.findChild("QDialogButtonBox", "buttonBox")
        buttonBox.connect("accepted()", self.grabNotes)
        buttonBox.connect("rejected()", self.cancelNotes)
        # Evaluation subsection
        self.imageQAWidget = self.loadUIFile('Resources/UI/queryQACollapsibleButton.ui')
        qaLayout = qt.QVBoxLayout(self.imageQAWidget)
        qaLayout.addWidget(self.imageQAWidget.findChild("QFrame", "titleFrame"))
        qaLayout.addWidget(self.imageQAWidget.findChild("QFrame", "tableVLine"))
        # Create review buttons on the fly
        for question in self.htmlFileName:
            reviewButton = self.reviewButtonFactory(question)
            qaLayout.addWidget(reviewButton)
            self.enableRadios(question)
        # DWI display widget
        self.dwiWidget = slicer.modulewidget.qSlicerDiffusionWeightedVolumeDisplayWidget()
        qaLayout.addWidget(self.dwiWidget)
        # batch button
        self.nextButton = qt.QPushButton()
        self.nextButton.setText('Get next raw DWI')
        self.nextButton.connect('clicked(bool)', self.onGetBatchFilesClicked)
        qaLayout.addWidget(self.nextButton)
        # Add all to layout
        self.layout.addWidget(self.imageQAWidget)
        self.layout.addWidget(self.dwiWidget)
        self.layout.addStretch(1)
        # Get popup window widget
        self.gradientDisplayWidget = self.loadUIFile('Resources/UI/notesDialog.ui')
        # Initialize data
        self.logic.onGetBatchFilesClicked()

    def loadUIFile(self, fileName):
        """ Return the object defined in the Qt Designer file """
        uiloader = qt.QUiLoader()
        qfile = qt.QFile(os.path.join(__slicer_module__, fileName))
        qfile.open(qt.QFile.ReadOnly)
        try:
            return uiloader.load(qfile)
        finally:
            qfile.close()

    def reviewButtonFactory(self, question):
        widget = self.loadUIFile('Resources/UI/dwiRawQuestionWidget.ui')
        # Set question label text
        questionLabel= widget.findChild("QLabel", "questionTextLabel")
        questionLabel.objectName = question
        questionLabel.setText(self._readHTML(question))
        # Set and rename radio buttons
        radioContainer = widget.findChild("QWidget", "radioWidget")
        radioContainer.objectName = question + "_radioWidget"
        yesButton = widget.findChild("QRadioButton", "yesButton")
        yesButton.objectName = question + "_yes"
        noButton = widget.findChild("QRadioButton", "noButton")
        noButton.objectName = question + "_no"
        return widget

    def _readCSS(self):
        fullPath = os.path.join(__slicer_module__,
                                'Resources/HTML',
                                'dwi_raw.css')
        fID = open(fullPath)
        try:
            self.css = fID.read()
        finally:
            fID.close()

    def _readHTML(self, question):
        if self.css is None:
            self._readCSS()
        fullPath = os.path.join(__slicer_module__,
                                'Resources/HTML',
                                question + '.html')
        fID = open(fullPath)
        text = ''
        try:
            text = fID.read()
        finally:
            fID.close()
        if not text == '':
            text = re.sub(r'CSS_FILE', self.css, text)
        return text

    # def connectSessionButtons(self):
    #     """ Connect the session navigation buttons to their logic """
    #     self.quitButton.connect('clicked()', self.exit)

    def enableRadios(self, question):
        """ Enable the radio buttons that match the given region name """
        self.imageQAWidget.findChild("QWidget", question + "_radioWidget").setEnabled(True)
        for suffix in ("_yes", "_no"):
            radio = self.imageQAWidget.findChild("QRadioButton", question + suffix)
            radio.setShortcutEnabled(True)
            radio.setCheckable(True)
            radio.setEnabled(True)

    def resetRadioWidgets(self):
        """ Disable and reset all radio buttons in the widget """
        print "Resetting radio buttons..."
        radios = self.imageQAWidget.findChildren("QRadioButton")
        for question in self.htmlFileName:
            for radio in radios:
                if radio.objectName.find(question) > -1 and radio.checked:
                    # Fix for a bug in QT: see http://qtforum.org/article/19619/qradiobutton-setchecked-bug.html
                    radio.setCheckable(False)
                    radio.update()
                    radio.setCheckable(True)
                    # This SHOULD reset the autoexclusive radio buttons...
                    if radio.isChecked():
                        raise Exception("Radio is NOT reset!")
                    else:
                        print "Resetting radio {0}...".format(radio.objectName)

    def getRadioValues(self):
        values = ()
        needsFollowUp = False
        radios = self.imageQAWidget.findChildren("QRadioButton")
        for question in self.htmlFileName:
            for radio in radios:
                if radio.objectName.find(question) > -1 and radio.checked:
                    if radio.objectName.find("_yes") > -1:
                        values = values + (True,)
                    elif radio.objectName.find("_no") > -1:
                        values = values + (False,)
                    else:
                        values = values + ("NULL",)
                        print "Warning: No value for %s" % question
        self.followUpDialog.exec_()
        if self.followUpDialog.result() and not self.notes is None:
            return values + (self.notes,)
        else:
            return values + ("NULL",)

    def resetWidget(self):
        print "Resetting widgets..."
        self.resetRadioWidgets()
        self.gradientDisplayWidget.close()
        self.resetClipboard()

    def grabNotes(self):
        self.notes = None
        self.notes = str(self.textEditor.toPlainText())
        # TODO: Format notes
        ### if self.notes = '':
        ###     self.followUpDialog.show()
        ###     self.textEditor.setText("A comment is required!")

    def cancelNotes(self):
        # TODO:
        pass

    def resetClipboard(self):
        self.clipboard.clear()

    def getValues(self):
        values = self.getRadioValues()
        return values

    def checkValues(self):
        values = self.getValues()
        if len(values) == len(self.htmlFileName) + 1:
            self.resetWidget()
            return (0, values)
        elif len(values) == 0:
            print "No values at all!"
            return (-1, values)
        else:
            # TODO: Handle this case intelligently
            print "Not enough values for the required columns!"
            print values
        return (-2, values)

    def onGetBatchFilesClicked(self):
        (code, values) = self.checkValues()
        if code == 0:
            self.logic.writeToDatabase(values)
            self.gradientDisplayWidget.close()
            self.logic.onGetBatchFilesClicked()
        else:
            pass

    def exit(self):
        """ When Slicer exits, prompt user if they want to write the last evaluation """
        (code, values) = self.checkValues()
        if code == 0:
            # TODO: Write a confirmation dialog popup
            self.logic.writeToDatabase(values)
            self.logic.exit()
            # self.logic.onGetBatchFilesClicked()
        elif code == -1:
            self.logic.exit()
        else:
            # TODO: write a prompt window
            self.logic.exit()
            # TODO: clear scene
        self.gradientDisplayWidget.close()

    def displayGradients(self, gradients):
        string = '\n'.join(item for item in gradients)
        self.gradientDisplayWidget.setWindowTitle('Gradient directions: %s' % self.logic.sessionFile['file'])
        editor = self.gradientDisplayWidget.findChild('QTextEdit')
        editor.setText(string)
        editor.setReadOnly(True)
        self.gradientDisplayWidget.show()
