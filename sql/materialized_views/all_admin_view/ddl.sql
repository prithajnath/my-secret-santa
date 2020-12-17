CREATE EXTENSION IF NOT EXISTS "uuid-ossp"; CREATE MATERIALIZED VIEW all_admin_view AS(
WITH admins AS
    (SELECT user_id,
         group_id
    FROM groups_and_users
    WHERE group_admin = 't' )
    SELECT uuid_generate_v4() AS id,
         user_id,
         username,
         group_id,
         groups.name AS groupname
    FROM users
    INNER JOIN admins
        ON users.id = admins.user_id
    INNER JOIN groups
        ON groups.id = admins.group_id ); CREATE UNIQUE INDEX
    ON all_admin_view (id); 