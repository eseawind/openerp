#!/usr/bin/env python
# -*- coding: utf-8 -*-

import optparse,os,re,sys,urllib2

def lpdownload(repo,name):
    url1 = "http://bazaar.launchpad.net/%s/view/head:/%s"%(repo,name)
    print "dl",url1
    page = urllib2.urlopen(url1).read()
    url = re.search("/%s/download/head:/.*?/%s"%(repo,name),page).group(0)
    print "dl",url
    return urllib2.urlopen("http://bazaar.launchpad.net%s"%url).read()

def autoupdate():
    open("Makefile","wb").write(lpdownload("~openerp/openerp/rdtools","Makefile"))
    open("Makefile_helper.py","wb").write(lpdownload("~openerp/openerp/rdtools","Makefile_helper.py"))

def pull(branch, folder):
    command = "bzr branch %s %s" % (branch, folder)
    print command
    os.system(command)

def push(branch, folder):
    command = "bzr push -d %s %s" % (folder, branch)
    print command
    os.system(command)

def branch(cmd):
    author = raw_input("author (eg : tfr): ")
    launchpad_project = { 1 :  'addons', 2 : 'client', 3: 'client-web', 4 : 'server'}
    launchpad = input("launchpad project (1 : addons, 2 : client, 3 : client-web, 4: server) : ")
    launchpad = launchpad_project[launchpad]
    if cmd.startswith("branch-project"):
        name = raw_input("project name: ")
        if cmd  == "branch-project-bug":
            number = raw_input("bug number: ")
            branch = "trunk-%s-bug-%s-%s" % (name, number, author)
        else:
            feature = raw_input("feature name: ")
            branch = "trunk-%s-%s-%s" % ( name, feature, author)
        if launchpad == 'client-web':
            branch_pull =  "lp:~openerp-dev/openerp-web/trunk-%s" % (name)
        else:
            branch_pull = "lp:~openerp-dev/openobject-%s/trunk-%s" % (launchpad, name)

    if cmd.startswith("branch-trunk"):
        if cmd.startswith("branch-trunk-bug"):
            number = raw_input("bug number :")
            branch = "trunk-bug-%s-%s" % (number, author)
        elif cmd.startswith("branch-trunk-feature"):
            feature = raw_input("feature name: ")
            branch = "trunk-%s-%s" % (feature, author)
        if launchpad == 'client-web':
            branch_pull =  "lp:~openerp-dev/openerp-web/trunk"
        else:
            branch_pull = "lp:~openerp/openobject-%s/trunk" % launchpad

    folder = "%s/%s" % (launchpad, branch)
    if launchpad == 'client-web':
        branch_push =  "lp:~openerp-dev/openerp-web/%s" %(branch)
    else:
        branch_push = "lp:~openerp-dev/openobject-%s/%s" % (launchpad, branch)

    pull(branch_pull, folder)
    push(branch_push, folder)

def main():
    parser = optparse.OptionParser()
    parser.add_option("", "--type", dest="type",default="project",help="type of branch needed")
    (o, a) = parser.parse_args()
    cmd = a[0]
    if cmd.startswith("autoupdate"):
        autoupdate()
    elif cmd.startswith("branch"):
        branch(cmd)

if __name__ == "__main__":
    main()
