#!/usr/bin/env python

"""
updatemanager.py -- checks for updates to tfutils on GitHub and retrieves them.
"""

import datetime
import json
import os
from os import path
import re
import tarfile
import time
import urllib

VERSIONS_DIR_PATH = path.join(path.dirname(path.abspath(__file__)), "versions")
TARBALL_DIR_PATH = path.join(VERSIONS_DIR_PATH, "tarballs")
BACKUP_DIR_PATH = path.join(VERSIONS_DIR_PATH, "backups")
ORIGIN_CONFIG_PATH = path.join(VERSIONS_DIR_PATH, "origin.js")
VERSIONS_INFO_PATH = path.join(VERSIONS_DIR_PATH, "versioninfo.js")
GITHUB_DOMAIN = "github.com"
UNPACK_DIR_PATH = path.dirname(path.dirname(path.abspath(__file__)))
BACKUP_SOURCE_DIR_PATH = path.dirname(path.abspath(__file__))

TARBALL_RE = re.compile(r"^tarball_\d{4}_\d{2}_\d{2}_\d{2}_\d{2}_\d{2}"
                        r"\.tar\.gz$")

DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S"
def parse_dt(sDt):
    return datetime.datetime.strptime(sDt.rsplit('-',1)[0], DATETIME_FORMAT)

class Commit(object):
    def __init__(self, id, sMessage, dt):
        self.id = id
        self.sMessage = sMessage
        self.dt = dt
    def to_json(self):
        return {"id":self.id, "message": self.sMessage,
                "committed_date": self.dt.isoformat()}
    @classmethod
    def from_json(self, dictCommit):
        dt = parse_dt(dictCommit["committed_date"])
        return Commit(dictCommit["id"], dictCommit["message"], dt)
    @classmethod
    def empty(cls):
        dt = datetime.datetime.fromtimestamp(0.0)
        return Commit("", "(No commit found.)", dt)
    def __repr__(self):
        return "Commit(%r,%r,%r)" % (self.id, self.sMessage, self.dt)

def github_api_call(*listArgs):
    listSPieces = [GITHUB_DOMAIN, "api", "v2", "json"] + list(listArgs)
    return "http://" + path.join(*listSPieces)

def github_last_commit(sUser,sRepo,sBranch):
    sUrl = github_api_call("commits", "list", sUser, sRepo, sBranch)
    infile = None
    try:
        infile = urllib.urlopen(sUrl)
        dictJson = json.load(infile)
    finally:
        infile.close()
    listCommit = map(Commit.from_json, dictJson["commits"])
    listCommit.sort(lambda a,b: -cmp(b.dt,a.dt))
    return (listCommit and listCommit[0]) or None

def tarball_filename():
    dt = datetime.datetime.now()
    tpl = (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second)
    return "tarball_%04d_%02d_%02d_%02d_%02d_%02d.tar.gz" % tpl

def github_tarball(sUser,sRepo,sBranch):
    return "https://" + path.join(GITHUB_DOMAIN, sUser, sRepo, "tarball",
                                  sBranch)

def load_origin_config(sPath=ORIGIN_CONFIG_PATH):
    with open(sPath) as infile:
        return json.load(infile)

def load_version_commit(sPath=VERSIONS_INFO_PATH):
    if not path.isfile(sPath):
        return Commit.empty()
    with open(sPath) as infile:
        return Commit.from_json(json.load(infile))

def latest_commit(dictOriginConfig, sBranchType):
    sUser = dictOriginConfig["user"]
    sRepo = dictOriginConfig["repo"]
    sBranch = dictOriginConfig["branches"][sBranchType]
    return github_last_commit(sUser,sRepo,sBranch)

def is_update_available(cmtLatest,cmtVersion):
    return cmtLatest.dt > cmtVersion.dt

def download_tarball(dictOriginConfig,sBranchType):
    sUser = dictOriginConfig["user"]
    sRepo = dictOriginConfig["repo"]
    sBranch = dictOriginConfig["branches"][sBranchType]
    sUrl = github_tarball(sUser,sRepo,sBranch)
    sFilename = tarball_filename()
    if not path.exists(TARBALL_DIR_PATH):
        os.makedirs(TARBALL_DIR_PATH)
    sFullFilename = path.join(TARBALL_DIR_PATH, sFilename)
    urllib.urlretrieve(sUrl, sFullFilename)
    return sFullFilename

def clean_downloads():
    for sFilename in os.listdir(TARBALL_DIR_PATH):
        if TARBALL_RE.match(sFilename) is not None:
            sFullPath = path.join(TARBALL_DIR_PATH, sFilename)
            os.unlink(sFullPath)
             
def check_for_updates():
    dictOriginConfig = load_origin_config()
    cmtLatest = latest_commit(dictOriginConfig, "master")
    cmtVersion = load_version_commit()
    return is_update_available(cmtLatest,cmtVersion)

def unpack_tarball(sTarballFilename, sUnpackOnto, sUser, sRepo):
    sReSrc = r'^%s-%s-\w+' % (re.escape(sUser), re.escape(sRepo))
    rePrefix = re.compile(sReSrc)
    tf = tarfile.open(sTarballFilename)
    for ti in tf.getmembers():
        ti.name = rePrefix.sub("tfutils",ti.name,1)
        tf.extract(ti,sUnpackOnto)
        
def backup_name():
    dt = datetime.datetime.now()
    return ("backup_%04d_%02d_%02d_%02d_%02d_%02d.tar.gz" %
            (dt.year, dt.month, dt.day, dt.hour, dt.minute, dt.second))

def filter_backup(sPath):
    return (BACKUP_DIR_PATH in sPath
            or TARBALL_DIR_PATH in sPath
            or "/build" in sPath
            or ".git/" in sPath
            or sPath.endswith(".pyc"))

def backup_current(sRoot):
    if not path.exists(BACKUP_DIR_PATH):
        os.makedirs(BACKUP_DIR_PATH)
    sFullFilename = path.join(BACKUP_DIR_PATH, backup_name())
    tf = tarfile.open(sFullFilename,"w:gz")
    tf.add(sRoot, path.basename(sRoot), exclude=filter_backup)
    tf.close()
    return sFullFilename

def update_version_info(cmt,sPath=VERSIONS_INFO_PATH):
    dictJs = cmt.to_json()
    with open(sPath, "wb") as outfile:
        json.dump(outfile,dictJs)

def deploy_updates():
    dictOriginConfig = load_origin_config()
    sFilename = download_tarball(dictOriginConfig,"master")
    unpack_tarball(sFilename, UNPACK_DIR_PATH, dictOriginConfig["user"],
                   dictOriginConfig["repo"])

def main(argv):
    #print check_for_updates()
    print backup_current(BACKUP_SOURCE_DIR_PATH)
    #deploy_updates()

if __name__ == "__main__":
    import sys
    sys.exit(main(sys.argv))
