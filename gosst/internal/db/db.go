package db

var Schema = `
	CREATE TABLE IF NOT EXISTS tokens (
		token TEXT NOT NULL
	);
	CREATE TABLE IF NOT EXISTS boards (
		id TEXT PRIMARY KEY,
		setup_id INTEGER NOT NULL,
		FOREIGN KEY (setup_id) REFERENCES setups (id)
	);
	CREATE TABLE IF NOT EXISTS setups(
		id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		linkage_id INTEGER NOT NULL,
		front_calibration_id INTEGER,
		rear_calibration_id INTEGER,
		FOREIGN KEY (linkage_id) REFERENCES linkages (linkage_id),
		FOREIGN KEY (front_calibration_id) REFERENCES calibrations (id),
		FOREIGN KEY (rear_calibration_id) REFERENCES calibrations (id)
	);
    CREATE TABLE IF NOT EXISTS calibrations (
        id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
        arm REAL NOT NULL,
        dist REAL NOT NULL,
        stroke REAL NOT NULL,
        angle REAL NOT NULL
    );
    CREATE TABLE IF NOT EXISTS linkages(
        id INTEGER PRIMARY KEY,
		name TEXT NOT NULL,
		raw_lr_data TEXT NOT NULL
	);
	CREATE TABLE IF NOT EXISTS tracks(
		id INTEGER PRIMARY KEY,
		track TEXT NOT NULL
	);
    CREATE TABLE IF NOT EXISTS sessions(
		id INTEGER PRIMARY KEY,
		name TEXT,
		setup_id INTEGER NOT NULL,
		description TEXT,
		timestamp INTEGER NOT NULL,
		data BLOB NOT NULL,
		track_id INTEGER,
		FOREIGN KEY (setup_id) REFERENCES setups (id),
		FOREIGN KEY (track_id) REFERENCES tracks (id)
	);
	CREATE TABLE IF NOT EXISTS bokeh_components(
		session_id INTEGER PRIMARY KEY,
		script TEXT NOT NULL,
		travel TEXT NOT NULL,
		velocity TEXT NOT NULL,
		map TEXT NOT NULL,
		lr TEXT NOT NULL,
		sw TEXT NOT NULL,
		setup TEXT NOT NULL,
		desc TEXT NOT NULL,
		f_thist TEXT NOT NULL,
		f_fft TEXT NOT NULL,
		f_vhist TEXT NOT NULL,
		r_thist TEXT NOT NULL,
		r_fft TEXT NOT NULL,
		r_vhist TEXT NOT NULL,
		cbalance TEXT NOT NULL,
		rbalance TEXT NOT NULL,
		FOREIGN KEY (session_id) REFERENCES sessions (id)
	);`

var SetupForBoard = `
	SELECT S.id, S.linkage_id, S.front_calibration_id, S.rear_calibration_id
	FROM setups S
	JOIN boards B
	WHERE
	    B.board_id = ?
		AND S.id = B.setup_id;`

var InsertBoard = `
	INSERT
	INTO boards (id, setup_id)
	VALUES (?, ?)
	RETURNING rowid`

var DeleteBoard = `
	DELETE
	FROM boards
	WHERE id = ?`

var Setups = `
	SELECT *
	FROM setups`

var Setup = `
	SELECT *
	FROM setups
	WHERE id = ?`

var InsertSetup = `
	INSERT
	INTO setups (name, linkage_id, front_calibration_id, rear_calibration_id)
	VALUES (?, ?, ?, ?)
	RETURNING id
	`
var DeleteSetup = `
	DELETE
	FROM setups
	WHERE id = ?`

var Calibrations = `
	SELECT *
	FROM calibrations`

var Calibration = `
	SELECT *
	FROM calibrations
	WHERE id = ?`

var InsertCalibration = `
	INSERT
	INTO calibrations (name, arm, dist, stroke, angle)
	VALUES (?, ?, ?, ?, ?)
	RETURNING id
	`
var DeleteCalibration = `
	DELETE
	FROM calibrations
	WHERE id = ?`

var Linkages = `
	SELECT *
	FROM linkages`

var Linkage = `
	SELECT *
	FROM linkages
	WHERE id = ?`

var InsertLinkage = `
	INSERT
	INTO linkages (name, raw_lr_data)
	VALUES (?, ?)
	RETURNING id`

var DeleteLinkage = `
	DELETE
	FROM linkages
	WHERE id = ?`

var Sessions = `
	SELECT id, name, timestamp, description, setup_id
	FROM sessions
	`
var Session = `
	SELECT id, name, timestamp, description, setup_id
	FROM sessions
	WHERE id = ?`

var SessionData = `
	SELECT name, data
	FROM sessions
	WHERE id = ?`

var InsertSession = `
	INSERT
	INTO sessions (name, timestamp, description, setup_id, data)
	VALUES (?, ?, ?, ?, ?)
	RETURNING id`

var DeleteSession = `
	DELETE
	FROM sessions
	WHERE id = ?`

var UpdateSession = `
	UPDATE sessions
	SET (name, description) = (?, ?)
	WHERE id = ?`
