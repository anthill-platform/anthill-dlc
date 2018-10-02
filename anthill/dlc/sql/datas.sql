CREATE TABLE `datas` (
  `data_id` int(11) unsigned NOT NULL AUTO_INCREMENT,
  `gamespace_id` int(10) unsigned NOT NULL,
  `application_name` varchar(255) NOT NULL DEFAULT '',
  `version_status` enum('CREATED','PUBLISHING','PUBLISHED','ERROR') NOT NULL DEFAULT 'CREATED',
  `version_status_reason` varchar(255) DEFAULT NULL,
  PRIMARY KEY (`data_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;