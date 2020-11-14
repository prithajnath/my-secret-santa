CREATE MATERIALIZED VIEW all_admin_view AS(
    WITH admins AS(
        SELECT
            user_id, group_id
        FROM 
            groups_and_users
        WHERE
            group_admin = 't'
    ) SELECT
        user_id,
        username,
        group_id,
        groups.name AS groupname
    FROM
        users
    INNER JOIN
        admins
    ON
        users.id = admins.user_id
    INNER JOIN
        groups
    ON
        groups.id = admins.group_id
);
