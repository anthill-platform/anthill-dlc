CREATE TABLE `data_bundles` (
  `gamespace_id` int(11) NOT NULL,
  `data_id` int(10) unsigned NOT NULL,
  `bundle_id` int(10) unsigned NOT NULL,
  UNIQUE KEY `data_id` (`data_id`,`bundle_id`),
  KEY `bundle_id` (`bundle_id`),
  CONSTRAINT `data_bundles_ibfk_1` FOREIGN KEY (`data_id`) REFERENCES `datas` (`data_id`),
  CONSTRAINT `data_bundles_ibfk_2` FOREIGN KEY (`bundle_id`) REFERENCES `bundles` (`bundle_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;