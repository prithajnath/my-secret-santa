CREATE MATERIALIZED VIEW all_latest_pairs_view AS(
    WITH all_latest_pairs AS (
        WITH latest_timestamps AS 
            (
                SELECT max(timestamp) AS max_timestamp,
                group_id
                FROM pairs
                GROUP BY  group_id
            )
            SELECT latest_timestamps.group_id,
                    giver_id,
                    receiver_id
            FROM latest_timestamps
            LEFT JOIN pairs 
                ON 
                    pairs.group_id = latest_timestamps.group_id
                AND
                    pairs.timestamp = latest_timestamps.max_timestamp
    )

    SELECT
        uuid_generate_v4() AS id,
        username,
        receiver_id,
        name as group_name
    FROM
        all_latest_pairs
    LEFT JOIN
        users
            ON
                users.id = all_latest_pairs.giver_id
    LEFT JOIN
        groups
            ON
                groups.id = all_latest_pairs.group_id
);

CREATE UNIQUE INDEX ON all_latest_pairs_view (id);
 

        
        
