CREATE TABLE `application_versions` (
  `application_name` varchar(255) NOT NULL DEFAULT '',
  `application_version` varchar(255) NOT NULL DEFAULT '',
  `current_data_version` int(11) DEFAULT NULL,
  KEY `application_idx` (`application_name`),
  CONSTRAINT `current_data_version_ibfk_1` FOREIGN KEY (`current_data_version`) REFERENCES `data_versions` (`version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;