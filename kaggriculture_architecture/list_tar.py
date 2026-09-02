import tarfile
tar = tarfile.open(r"C:\Coding\kaggriculture_architecture\submission\submission.tar.gz", "r:gz")
for m in tar.getmembers()[:10]:
    print(m.name)
