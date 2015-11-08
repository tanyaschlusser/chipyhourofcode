/* 
 * create_tables.sql
 *
 * We are using MySQL 5.5.42. This document creates all of
 * the tables that will be used in the database.
 */

CREATE TABLE IF NOT EXISTS attendee (
  id MEDIUMINT NOT NULL AUTO_INCREMENT,
  attendee_name varchar(64),
  guardian_email varchar(64),
  guardian_name varchar(64),
  registration_timestamp timestamp NOT NULL DEFAULT current_timestamp,
  PRIMARY KEY (id)
  UNIQUE INDEX child_guardian_pair (attendee_name, guardian_email);
);

CREATE TABLE IF NOT EXISTS speaker (
  id MEDIUMINT NOT NULL AUTO_INCREMENT,
  speaker_name varchar(64),
  img_path varchar(64),
  speaker_bio varchar(1024),
  PRIMARY KEY (id)
);
