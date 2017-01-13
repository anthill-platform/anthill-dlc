CREATE TABLE `application_versions` (
  `application_name` varchar(255) NOT NULL DEFAULT '',
  `application_version` varchar(255) NOT NULL DEFAULT '',
  `gamespace_id` int(11) unsigned NOT NULL,
  `current_data_version` int(11) unsigned DEFAULT NULL,
  UNIQUE KEY `application_name` (`application_name`,`gamespace_id`),
  KEY `application_idx` (`application_name`),
  KEY `current_data_version` (`current_data_version`),
  CONSTRAINT `application_versions_ibfk_1` FOREIGN KEY (`current_data_version`) REFERENCES `data_versions` (`version_id`)
) ENGINE=InnoDB CHARSET=utf8;