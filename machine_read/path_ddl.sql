--create schema-ddl
DROP TABLE IF EXISTS greentea_paths;
CREATE TABLE greentea_paths (
	id serial,
	path_type varchar NULL,
	path_start varchar NULL,
	path_start_label varchar null,
	path_end varchar NULL,
	path_end_label varchar null,
	path_count int4 NULL,
	path_step int4 NULL,
	subject_label varchar NULL,
	predicate_label varchar NULL,
	object_label varchar NULL,
	subject_uri varchar NULL,
	predicate_uri varchar NULL,
	object_uri varchar NULL,
	source_data varchar null,
	pub_year varchar null
);
\echo 'Starting transaction'
START TRANSACTION;
\echo 'Loading data into mediator_paths'
\copy greentea_paths (path_type, path_start, path_end, path_count, path_step, subject_label, predicate_label, object_label, 
subject_uri, predicate_uri, object_uri, source_file) from 'filename' DELIMITER E'\t' NULL '\\N' CSV HEADER;
COMMIT;

DROP TABLE IF EXISTS kratom_paths;
CREATE TABLE kratom_paths (
	id serial,
	path_type varchar NULL,
	path_start varchar NULL,
	path_start_label varchar null,
	path_end varchar NULL,
	path_end_label varchar null,
	path_count int4 NULL,
	path_step int4 NULL,
	subject_label varchar NULL,
	predicate_label varchar NULL,
	object_label varchar NULL,
	subject_uri varchar NULL,
	predicate_uri varchar NULL,
	object_uri varchar NULL,
	source_data varchar null,
	pub_year varchar null
);
\echo 'Starting transaction'
START TRANSACTION;
\echo 'Loading data into mediator_paths'
\copy kratom_paths (path_type, path_start, path_end, path_count, path_step, subject_label, predicate_label, object_label, 
subject_uri, predicate_uri, object_uri, source_file) from 'filename' DELIMITER E'\t' NULL '\\N' CSV HEADER;
COMMIT;