.PHONY: server web

help:
	@# Display help
	@grep -A1 '^[a-z0-9-]*:[^=]*$$' Makefile | grep -v ^--
autoupdate:
	# Autoupdate makefile
	bzr cat -d lp:~openerp-dev/openerp-tools/trunk setup.sh | sh

#--------------------------------------------------------------------
# Versioning
#--------------------------------------------------------------------
init: init-v70
	# Init repository and download sources for latest stable and trunk

init-trunk:
	# Init repository
	[ -d web ] || bzr colo-fetch lp:~openerp/openerp-web/trunk web
	[ -d addons ] || bzr colo-fetch lp:~openerp/openobject-addons/trunk addons
	[ -d server ] || bzr colo-fetch lp:~openerp/openobject-server/trunk server
	[ -d client ] || bzr colo-fetch lp:~openerp/openobject-client-web/trunk client
	#for dir in addons client client-web server misc web; do [ -d $${dir} ] || bzr colo-init $${dir}; done

init-v60: init-trunk
	[ -d addons/.bzr/branches/6.0 ]     || (cd addons && bzr branch lp:~openerp/openobject-addons/6.0 colo:6.0 && cd ..)
	[ -d client/.bzr/branches/6.0 ]     || (cd client && bzr branch lp:~openerp/openobject-client/6.0 colo:6.0 && cd ..)
	[ -d client-web ] || bzr colo-fetch lp:~openerp/openobject-client-web/6.0 client-web
	[ -d server/.bzr/branches/6.0 ]     || (cd server && bzr branch lp:~openerp/openobject-server/6.0 colo:6.0 && cd ..)

init-v61: init-trunk
	[ -d addons/.bzr/branches/6.1 ]     || (cd addons && bzr branch lp:~openerp/openobject-addons/6.1 colo:6.1 && cd ..)
	[ -d client/.bzr/branches/6.1 ]     || (cd client && bzr branch lp:~openerp/openobject-client/6.1 colo:6.1 && cd ..)
	[ -d web/.bzr/branches/6.1 ]        || (cd web && bzr branch lp:~openerp/openerp-web/6.1 colo:6.1 && cd ..)
	[ -d server/.bzr/branches/6.1 ]     || (cd server && bzr branch lp:~openerp/openobject-server/6.1 colo:6.1 && cd ..)

init-v70: init-trunk
	[ -d addons/.bzr/branches/7.0 ]     || (cd addons && bzr branch lp:~openerp/openobject-addons/7.0 colo:7.0 && bzr switch colo:7.0 && cd ..)
	[ -d web/.bzr/branches/7.0 ]        || (cd web && bzr branch lp:~openerp/openerp-web/7.0 colo:7.0 && bzr switch colo:7.0 && cd ..)
	[ -d server/.bzr/branches/7.0 ]     || (cd server && bzr branch lp:~openerp/openobject-server/7.0 colo:7.0 && bzr switch colo:7.0 && cd ..)

pull:
	# update all trunk branch
	for i in addons client oldweb web server; do [ -d $$i ] && (cd $$i && bzr pull && cd ..); done

switch-to-trunk:
	for i in addons client oldweb web server; do [ -d $$i ] && (cd $$i && bzr switch origin/trunk && cd ..); done

switch-to-60:
	for i in addons client oldweb web server; do [ -d $$i ] && (cd $$i && bzr switch colo:6.0 && cd ..); done

switch-to-61:
	for i in addons client oldweb web server; do [ -d $$i ] && (cd $$i && bzr switch colo:6.1 && cd ..); done

branch-project-feature:
	# create a branch to work on a feature on a given project
	python Makefile_helper.py branch-project-feature
branch-project-bug:
	# create a branch to work on a bug related to a project
	python Makefile_helper.py branch-project-bug
branch-trunk-feature:
	# create a branch to work on a single feature on trunk
	python Makefile_helper.py branch-trunk-feature
branch-trunk-bug:
	# create a branch to work on a given bugs on trunk
	python Makefile_helper.py branch-trunk-bug

#--------------------------------------------------------------------
# DB
#--------------------------------------------------------------------
time:=$(shell date +%Y%m%d-%H%M%S)
DBNAME:=$(shell psql -l -A -t -F. | fgrep .$$USER. | cut -d. -f1 | sort -n | tail -1)
dbsetup:
	# setup a postgres user
	sudo su - postgres -c "createuser -s $$USER"
dbdump:
	# dump the last db
	echo ${DBNAME}
	time pg_dump ${DBNAME} | gzip -9 > dump/${DBNAME}.${time}.sql.gz && ln -sf ${DBNAME}.${time}.sql.gz dump/${DBNAME}.last.sql.gz
dbrestore:
	# restore the last backup of the last db
	#sudo restart postgresql
	dropdb ${DBNAME} || true
	createdb ${DBNAME}
	zcat dump/${DBNAME}.last.sql.gz | psql ${DBNAME}
dbdumpall:
	# dump all databases
	for I in `psql -l -A -t -F. | fgrep .$$USER. | cut '-d.' -f1`; do echo dumping $$I; time pg_dump $$I | gzip -9 > dump/$$I.${time}.sql.gz; ln -sf $$I.${time}.sql.gz dump/$$I.last.sql.gz; done
dbdroptrunk:
	# drop all databases named trunk*
	psql -l | grep trunk |cut -d \| -f1  | xargs -n1 dropdb

#--------------------------------------------------------------------
# OpenERP server and client
#--------------------------------------------------------------------
SERVER_BIN=./server/openerp-server
SERVER_OPTIONS=--addons-path=addons,web/addons

SERVER_OPTIONS += --log-level=debug
#SERVER_OPTIONS += --log-level=debug_rpc
#SERVER_OPTIONS += --log-level=debug_rpc_answer
#SERVER_OPTIONS += --test-enable

SERVER_UPDATE=-d ${DBNAME} -u base

oldweb:
	# launch the old web client
	./client-web/openerp-web.py
gtk:
	# launch the gtk client
	./client/bin/openerp-client.py
server:
	# launch the server
	${SERVER_BIN} ${SERVER_OPTIONS}
server-log:
	# launch the server and log to server.log
	${SERVER_BIN} ${SERVER_OPTIONS} >> server.log
server-update:
	# launch the server to update the last db and log to server.log
	${SERVER_BIN} ${SERVER_OPTIONS} ${SERVER_UPDATE} >> server.log
server-tail:
	# less the server.log use F in less to enable follow mode
	less server.log

