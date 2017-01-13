CREATE TABLE `applications` (
  `application_name` varchar(255) NOT NULL DEFAULT '',
  `gamespace_id` int(10) unsigned NOT NULL,
  `deployment_method` varchar(64) NOT NULL DEFAULT '',
  `deployment_data` json NOT NULL,
  PRIMARY KEY (`application_name`),
  UNIQUE KEY `application_name` (`application_name`,`gamespace_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8;