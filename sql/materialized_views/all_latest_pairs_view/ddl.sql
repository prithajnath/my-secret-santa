CREATE MATERIALIZED VIEW all_latest_pairs_view AS(
    WITH cte1 AS (
        SELECT 
            c.username AS giver_username, 
            b.username AS receiver_username, 
            d.name AS group_name, 
            a.channel_id,
            a.timestamp AS created_at,
            RANK() OVER (PARTITION BY group_id ORDER BY timestamp DESC) AS r 
        FROM 
            pairs a 
        LEFT JOIN 
            users b 
        ON a.receiver_id = b.id 
        LEFT JOIN users c 
        ON a.giver_id = c.id 
        LEFT JOIN groups d 
        ON a.group_id = d.id
    ) SELECT 
        uuid_generate_v4() AS id,
        giver_username, 
        receiver_username, 
        channel_id,
        created_at,
        group_name 
    FROM cte1 WHERE r = 1
);

CREATE UNIQUE INDEX ON all_latest_pairs_view (id);
 

        
        
