package db

var SetupForBoard = `
	SELECT S.id, S.linkage_id, S.front_calibration_id, S.rear_calibration_id
	FROM setup S
	JOIN board B
	ON S.id = B.setup_id
	WHERE
	    B.id = ?
		AND S.id = B.setup_id
		AND S.deleted IS NULL
		AND B.deleted IS NULL;`

var InsertBoard = `
	INSERT OR IGNORE
	INTO board (id, setup_id, updated)
	VALUES (?, ?, ?);`

var Setup = `
	SELECT linkage_id, front_calibration_id, rear_calibration_id
	FROM setup
	WHERE id = ? AND deleted IS NULL;`

var CalibrationMethod = `
	SELECT *
	FROM calibration_method
	WHERE id = ? AND deleted IS NULL;`

var Calibration = `
	SELECT *
	FROM calibration
	WHERE id = ? AND deleted IS NULL;`

var Linkage = `
	SELECT *
	FROM linkage
	WHERE id = ? AND deleted IS NULL;`

var InsertSession = `
	INSERT
	INTO session (id, name, timestamp, description, setup_id, data, updated)
	VALUES (?, ?, ?, ?, ?, ?, ?)`
