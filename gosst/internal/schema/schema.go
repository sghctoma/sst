package schema

var Sql = `
	CREATE TABLE IF NOT EXISTS boards (
		board_id TEXT PRIMARY KEY,
		setup_id INTEGER NOT NULL,
		FOREIGN KEY (setup_id) REFERENCES setups (setup_id)
	);
	CREATE TABLE IF NOT EXISTS setups(
		setup_id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		linkage_id INTEGER NOT NULL,
		front_calibration_id INTEGER NOT NULL,
		rear_calibration_id INTEGER NOT NULL,
		FOREIGN KEY (linkage_id) REFERENCES linkages (linkage_id)
		FOREIGN KEY (front_calibration_id) REFERENCES calibrations (calibration_id)
		FOREIGN KEY (rear_calibration_id) REFERENCES calibrations (calibration_id)
	);
    CREATE TABLE IF NOT EXISTS calibrations (
        calibration_id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
        arm REAL NOT NULL,
        dist REAL NOT NULL,
        stroke REAL NOT NULL,
        angle REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS linkages(
        linkage_id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		raw_lr_data TEXT NOT NULL
	);
    CREATE TABLE IF NOT EXISTS sessions(
		session_id INTEGER PRIMARY KEY,
		name TEXT,
		setup_id INTEGER NOT NULL,
		description TEXT,
		timestamp INTEGER,
		data BLOB,
		FOREIGN KEY (setup_id) REFERENCES setups (setup_id));`