CREATE TABLE `bundles` (
  `bundle_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `version_id` int(11) unsigned NOT NULL,
  `gamespace_id` int(11) unsigned NOT NULL,
  `bundle_name` varchar(128) NOT NULL,
  `bundle_url` varchar(512) DEFAULT NULL,
  `bundle_size` int(11) unsigned NOT NULL DEFAULT '0',
  `bundle_hash` varchar(64) DEFAULT NULL,
  `bundle_status` enum('CREATED','UPLOADED','DELIVERING','DELIVERED','ERROR') NOT NULL DEFAULT 'CREATED',
  PRIMARY KEY (`bundle_id`),
  KEY `version_idx` (`version_id`),
  CONSTRAINT `bundles_ibfk_1` FOREIGN KEY (`version_id`) REFERENCES `data_versions` (`version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;