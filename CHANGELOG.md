CHANGELOG
=========

Version 0.1, 2014-04-10
-----------------------
- BUG: Derived images no longer fails for T1-only sessions
- BUG: Fixed labels to come from combined label segmentation file 'allLabels_seg'
- BUG: Fixed radio reset in DWIPreprocessing
- BUG: Fix notes in DWIrawQA module
- ENH: integrated roboRater results with DerivedImages
- ENH: cleaned up notes created with Derived Images
- BUG: Fixed bug introduced while renaming notesDialog.ui file
- BUG: Generalized DerivedImages loadingfor scans with and without roboRater reviews
- BUG: Converted pg8000 to submodule to ease upgrading.  Removed hardcoded version number from code
- BUG: Fixed DWIPreprocessing text editing bug (HEAD, master)
