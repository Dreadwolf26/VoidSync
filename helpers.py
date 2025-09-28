import stat

def recursive_rmdir(sftp, path):
    for entry in sftp.listdir_attr(path):
        subpath = f"{path}/{entry.filename}"
        if stat.S_ISDIR(entry.st_mode):
            recursive_rmdir(sftp, subpath)
        else:
            sftp.remove(subpath)
    sftp.rmdir(path)
