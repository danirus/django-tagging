import unittest

def suite():
    from django.db.models.loading import load_app
    from django.conf import settings

    from tagging.tests import tests

    testsuite = unittest.TestSuite([
        unittest.TestLoader().loadTestsFromModule(tests),
    ])
    return testsuite
