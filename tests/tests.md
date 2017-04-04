Tests
======

Initial set of tests


# setup

    sudo -u postgres createdb wibble

    sudo -u postgres psql -c '
    CREATE TABLE wibbletest (
        wibbletest boolean
    );' wibble


## direct content test

playbook:-

    - name: direct content test
      postgresql_exec:
        database: wibble
        content: 'insert into wibbletest (wibbletest) values (true);'

check:-

    sudo -u postgres psql -c 'select count(*) from wibbletest' wibble
