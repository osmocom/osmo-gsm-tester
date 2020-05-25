class ExpectedFail(Exception):
    pass
raise ExpectedFail('This failure is expected')
