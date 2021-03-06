django-tagging
==============

This is a generic tagging application for django projects. It's a fork of `brosner's one <https://github.com/brosner/django-tagging>`_ that adds Python 3 compatibility. 

Does not contain sweeteners. Tests passed under:

* Python 3.2 and django 1.5.1
* Python 2.7 and django 1.5.1
* Python 2.7 and django 1.4.5

Original code written by:

* `Jonathan Buchanan <https://github.com/insin>`_
* `Brian Rosner <https://github.com/brosner>`_
* `Doug Napoleone <https://github.com/dougn>`_
* `Devin Carlen <https://github.com/devcamcar>`_
* `Jacob Kaplan-Moss <https://github.com/jacobian>`_

For installation instructions, see the file "INSTALL.rst" in this
directory; for instructions on how to use this application, and on
what it provides, see the file "overview.txt" in the "docs/"
directory.

Includes a **test suite**. If you commit code, please consider adding proper coverage (especially if it has a chance for a regression) in the test suite.

Run the tests with:  ``django-admin.py test tagging --settings=tagging.tests.settings --verbosity=2``
