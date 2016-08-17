CREATE TABLE `data_versions` (
  `version_id` int(11) NOT NULL AUTO_INCREMENT,
  `application_name` varchar(255) NOT NULL DEFAULT '',
  `version_status` enum('created','completed') NOT NULL DEFAULT 'created',
  PRIMARY KEY (`version_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;