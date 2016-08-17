CREATE TABLE `bundles` (
  `bundle_id` int(11) NOT NULL AUTO_INCREMENT,
  `version_id` int(11) NOT NULL,
  `bundle_name` varchar(128) NOT NULL,
  `bundle_url` varchar(512) DEFAULT NULL,
  `bundle_hash` varchar(64) DEFAULT NULL,
  PRIMARY KEY (`bundle_id`),
  KEY `version_idx` (`version_id`),
  CONSTRAINT `version_id_ibfk_1` FOREIGN KEY (`version_id`) REFERENCES `data_versions` (`version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;