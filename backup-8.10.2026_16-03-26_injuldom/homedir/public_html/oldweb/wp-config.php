<?php
/**
 * The base configuration for WordPress
 *
 * The wp-config.php creation script uses this file during the
 * installation. You don't have to use the web site, you can
 * copy this file to "wp-config.php" and fill in the values.
 *
 * This file contains the following configurations:
 *
 * * MySQL settings
 * * Secret keys
 * * Database table prefix
 * * ABSPATH
 *
 * @link https://codex.wordpress.org/Editing_wp-config.php
 *
 * @package WordPress
 */

// ** MySQL settings - You can get this info from your web host ** //
/** The name of the database for WordPress */
define('DB_NAME', 'injuldom_wp339');

/** MySQL database username */
define('DB_USER', 'injuldom_wp339');

/** MySQL database password */
define('DB_PASSWORD', 'pSD9f)[X79');

/** MySQL hostname */
define('DB_HOST', 'localhost');

/** Database Charset to use in creating database tables. */
define('DB_CHARSET', 'utf8mb4');

/** The Database Collate type. Don't change this if in doubt. */
define('DB_COLLATE', '');

/**#@+
 * Authentication Unique Keys and Salts.
 *
 * Change these to different unique phrases!
 * You can generate these using the {@link https://api.wordpress.org/secret-key/1.1/salt/ WordPress.org secret-key service}
 * You can change these at any point in time to invalidate all existing cookies. This will force all users to have to log in again.
 *
 * @since 2.6.0
 */
define('AUTH_KEY',         'mm3s2iifjmpvy01ijagdeqjrkmjdbt4ncbnye121orfbgpmwsmrq6sk7phxa1eqt');
define('SECURE_AUTH_KEY',  'qlqmt8uaalwj23vnhil0qtypyyuzrndqeabz0rsyim45nfjadppnxp97ge7jhevs');
define('LOGGED_IN_KEY',    'rjzeaqmhtfpks6gdqjhfyebinyv78rpl6msscztj1ff7sr4eccwibwrpemfwve9n');
define('NONCE_KEY',        '42o9pxvyqetnm7hleo6wb2cckzvpc1ll6ja8amxtada2hukybu28tnl9a82asazj');
define('AUTH_SALT',        'vusucejd447rioahfaqn5imdmrpcdqwgyukfyuw5bjuvqt6hxkbvyaomehiwqrwm');
define('SECURE_AUTH_SALT', 'u7v79lfcsns8cwduntyuppglxd8gurt1nayc9embsxuwni8ispx07hxda8jt04tj');
define('LOGGED_IN_SALT',   'zku9tad6lhbov7zjjl3l0tplhhlnl0gbnexgcrmiep4a3gv6gqzh1ig7l7mgoqgg');
define('NONCE_SALT',       'afyolfde4nmtvidy58clz9i49dwzzqq4tcm5vjqgveclqmikjrrfclytjmvt1fj7');

/**#@-*/

/**
 * WordPress Database Table prefix.
 *
 * You can have multiple installations in one database if you give each
 * a unique prefix. Only numbers, letters, and underscores please!
 */
$table_prefix  = 'wpux_';

/**
 * For developers: WordPress debugging mode.
 *
 * Change this to true to enable the display of notices during development.
 * It is strongly recommended that plugin and theme developers use WP_DEBUG
 * in their development environments.
 *
 * For information on other constants that can be used for debugging,
 * visit the Codex.
 *
 * @link https://codex.wordpress.org/Debugging_in_WordPress
 */
define('WP_DEBUG', false);

/* That's all, stop editing! Happy blogging. */

/** Absolute path to the WordPress directory. */
if ( !defined('ABSPATH') )
	define('ABSPATH', dirname(__FILE__) . '/');

/** Sets up WordPress vars and included files. */
require_once(ABSPATH . 'wp-settings.php');
