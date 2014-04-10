cmake_minimum_required(VERSION 2.8.7)

#-----------------------------------------------------------------------------
if(NOT Slicer_SOURCE_DIR)
  set(EXTENSION_NAME DerivedImageQA)
  set(EXTENSION_HOMEPAGE "http://www.slicer.org/slicerWiki/index.php/Documentation/4.1/Extensions/DerivedImageQA")
  set(EXTENSION_CATEGORY "Work in Progress")
  set(EXTENSION_STATUS "Beta")
  set(EXTENSION_CONTRIBUTORS "Dave Welch (UIowa), Hans Johnson (UIowa)")
  set(EXTENSION_DESCRIPTION "A Slicer-based evaluation module for BRAINS AutoWorkup results")
  set(EXTENSION_ICONURL "http://viewvc.slicer.org/viewvc.cgi/Slicer4/trunk/Extensions/Testing/SlicerDerivedImageEval/Resources/Icons/DerivedImageQA.png?revision=19437&view=co")
  set(EXTENSION_SCREENSHOTURLS "http://wiki.slicer.org/slicerWiki/images/e/e2/Slicer-r19441-DerivedImageQA-screenshot.png")
endif()

#-----------------------------------------------------------------------------
set(MODULE_NAME DerivedImageQA)

#-----------------------------------------------------------------------------
if(NOT Slicer_SOURCE_DIR)
  find_package(Slicer REQUIRED)
  include(${Slicer_USE_FILE})
endif()

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  DerivedImageQA.py
  derived_logic.py
  derived_helper.py
  module_locator.py
  )

set(MODULE_PYTHON_RESOURCES
  Python/pg8000/pg8000/__init__.py
  )

#-----------------------------------------------------------------------------
ctkMacroCompilePythonScript(
  TARGET_NAME DerivedImageQA
  SCRIPTS "${MODULE_PYTHON_SCRIPTS}"
  RESOURCES "${MODULE_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}
  NO_INSTALL_SUBDIR
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()

#-----------------------------------------------------------------------------
if(NOT Slicer_SOURCE_DIR)
  include(${Slicer_EXTENSION_CPACK})
endif()

#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------

if(NOT Slicer_SOURCE_DIR)
  set(EXTENSION_NAME DWIPreprocessingQA)
  set(EXTENSION_HOMEPAGE "http://www.slicer.org/slicerWiki/index.php/Documentation/4.1/Extensions/DWIPreprocessingQA")
  set(EXTENSION_CATEGORY "Quality Assurance")
  set(EXTENSION_STATUS "Beta")
  set(EXTENSION_CONTRIBUTORS "Dave Welch (UIowa), Hans Johnson (UIowa)")
  set(EXTENSION_DESCRIPTION "A Slicer-based evaluation module for DWI pre-processing")
  set(EXTENSION_ICONURL "http://viewvc.slicer.org/viewvc.cgi/Slicer4/trunk/Extensions/Testing/DWIPreprocessingQA/Resources/Icons/DWIPreprocessingQA.png?revision=19437&view=co")
  set(EXTENSION_SCREENSHOTURLS "http://wiki.slicer.org/slicerWiki/images/e/e2/Slicer-r19441-DWIPreprocessingQA-screenshot.png")
endif()

#-----------------------------------------------------------------------------
set(MODULE_NAME DWIPreprocessingQA)

#-----------------------------------------------------------------------------
if(NOT Slicer_SOURCE_DIR)
  find_package(Slicer REQUIRED)
  include(${Slicer_USE_FILE})
endif()

#-----------------------------------------------------------------------------
set(MODULE_PYTHON_SCRIPTS
  DWIPreprocessingQA.py
  dwi_logic.py
  dwi_helper.py
  )

set(MODULE_PYTHON_RESOURCES
  Python/pg8000/pg8000/__init__.py
  module_locator.py
  )

#-----------------------------------------------------------------------------
ctkMacroCompilePythonScript(
  TARGET_NAME DWIPreprocessingQA
  SCRIPTS "${MODULE_PYTHON_SCRIPTS}"
  RESOURCES "${MODULE_PYTHON_RESOURCES}"
  DESTINATION_DIR ${CMAKE_BINARY_DIR}/${Slicer_QTSCRIPTEDMODULES_LIB_DIR}
  INSTALL_DIR ${Slicer_INSTALL_QTSCRIPTEDMODULES_LIB_DIR}
  NO_INSTALL_SUBDIR
  )

#-----------------------------------------------------------------------------
if(BUILD_TESTING)
  add_subdirectory(Testing)
endif()

#-----------------------------------------------------------------------------
if(NOT Slicer_SOURCE_DIR)
  include(${Slicer_EXTENSION_CPACK})
endif()

