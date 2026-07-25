# Provides RAKSHAK support for run pytests.
import sys, pytest
if __name__ == '__main__':
    sys.exit(pytest.main(['-q', 'tests']))
