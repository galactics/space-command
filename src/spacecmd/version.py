

def spacecmd_version(*args):
    """\
    Show version of the space-command utility
    """

    import spacecmd
    import beyond

    print("Space-Command  {}".format(spacecmd.__version__))
    print("Beyond         {}".format(beyond.__version__))
