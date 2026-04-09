#!/bin/sh
set -eu

echo "Waiting for mysql-primary..."
until mysqladmin ping -h mysql-primary -uroot -p"${MYSQL_ROOT_PASSWORD}" --silent; do
  sleep 2
done

echo "Waiting for mysql-replica..."
until mysqladmin ping -h mysql-replica -uroot -p"${MYSQL_ROOT_PASSWORD}" --silent; do
  sleep 2
done

echo "Configuring mysql-replica..."
mysql -h mysql-replica -uroot -p"${MYSQL_ROOT_PASSWORD}" <<SQL
SET GLOBAL super_read_only = OFF;
SET GLOBAL read_only = OFF;
STOP REPLICA;
RESET REPLICA ALL;
CHANGE REPLICATION SOURCE TO
  SOURCE_HOST='mysql-primary',
  SOURCE_PORT=3306,
  SOURCE_USER='${REPLICATION_USER}',
  SOURCE_PASSWORD='${REPLICATION_PASSWORD}',
  SOURCE_AUTO_POSITION=1,
  GET_SOURCE_PUBLIC_KEY=1;
START REPLICA;
SET GLOBAL read_only = ON;
SET GLOBAL super_read_only = ON;
SHOW REPLICA STATUS\G
SQL

echo "mysql-replica configured."
