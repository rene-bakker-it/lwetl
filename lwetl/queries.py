content_queries = {
    # ORACLE
    # =================================================================================================
    'oracle': '''
SELECT
    t.TABLE_NAME,
    t.COLUMN_NAME,
    CASE
        WHEN r.CONSTRAINT_TYPE = 'P' THEN 'PK'
        WHEN r.CONSTRAINT_TYPE = 'R' THEN 'FK'
        ELSE '' 
    END AS KEY_TYPE,
    t.DATA_TYPE,
    t.DATA_LENGTH,
    t.NULLABLE,
    rr.TABLE_NAME AS FK_TABLE,
    tc.COLUMN_NAME AS FK_COLUMN,
    NVL(c.CONSTRAINT_NAME,i.INDEX_NAME) AS CONSTRAINT_NAME,
    ut.NUM_ROWS,
    t.NUM_DISTINCT
FROM
    COLS t
    INNER JOIN USER_TABLES ut ON ut.TABLE_NAME = t.TABLE_NAME
    LEFT JOIN ALL_CONS_COLUMNS c
        INNER JOIN ALL_CONSTRAINTS r
            LEFT JOIN ALL_CONSTRAINTS rr 
                INNER JOIN ALL_CONS_COLUMNS tc ON tc.CONSTRAINT_NAME = rr.CONSTRAINT_NAME
            ON rr.OWNER=r.OWNER AND rr.CONSTRAINT_NAME=r.R_CONSTRAINT_NAME AND r.CONSTRAINT_TYPE = 'R'
        ON r.OWNER=c.OWNER AND r.CONSTRAINT_NAME=c.CONSTRAINT_NAME AND r.CONSTRAINT_TYPE IN ('P','R')
    ON c.TABLE_NAME=t.TABLE_NAME AND c.COLUMN_NAME=t.COLUMN_NAME
    LEFT JOIN ALL_IND_COLUMNS i ON i.TABLE_NAME = t.TABLE_NAME AND i.COLUMN_NAME=t.COLUMN_NAME
ORDER BY
    t.TABLE_NAME,
    CASE
        WHEN r.CONSTRAINT_TYPE = 'P' THEN 0
        WHEN r.CONSTRAINT_TYPE = 'R' THEN 1
        ELSE 2 
    END,
    t.COLUMN_NAME,
    NVL(c.CONSTRAINT_NAME,i.INDEX_NAME)''',

    # SQL SERVER
    # =================================================================================================
    'sqlserver': '''
SELECT
    t1.name as tableName,
    c1.name as columnName,
    CASE WHEN pk.object_id IS NULL
        THEN CASE WHEN sq.fkName IS NULL
                THEN NULL
                ELSE 'FK'
             END
        ELSE 'PK'
    END AS KEY_TYPE,
    dt.name AS DATA_TYPE,    
    CASE WHEN dt.name IN('nchar', 'nvarchar') AND c1.max_length <> -1
        THEN c1.max_length / 2
        ELSE c1.max_length
    END AS data_length,
    CASE WHEN c1.is_nullable=1 THEN 'Y' ELSE 'N' END AS nullable,
    sq.fkTableName,
    sq.fkColumnName,
    ISNULL(sq.fkName,pk.name) AS CONSTRAINT_NAME
FROM
    SYS.tables t1
    INNER JOIN SYS.all_columns c1 ON c1.OBJECT_ID = t1.OBJECT_ID
    LEFT OUTER JOIN SYS.indexes pk ON pk.object_id = c1.object_id AND pk.index_id = c1.column_id
    LEFT OUTER JOIN SYS.types ct ON ct.user_type_id = c1.user_type_id
    LEFT OUTER JOIN SYS.types dt ON dt.user_type_id = c1.system_type_id and dt.user_type_id = dt.system_type_id
    LEFT OUTER JOIN (
        SELECT
            CONVERT(SYSNAME, OBJECT_NAME(F.OBJECT_ID)) as fkName,
            CONVERT(SYSNAME, O1.NAME) as fkTableName,
            CONVERT(SYSNAME, C1.NAME) as fkColumnName,
            CONVERT(SYSNAME, O2.NAME) as pkTableName,
            CONVERT(SYSNAME, C2.NAME) as pkColumnName
        FROM
            SYS.ALL_OBJECTS O1,
            SYS.ALL_OBJECTS O2,
            SYS.ALL_COLUMNS C1,
            SYS.ALL_COLUMNS C2,
            SYS.FOREIGN_KEYS F
            INNER JOIN SYS.FOREIGN_KEY_COLUMNS K ON K.CONSTRAINT_OBJECT_ID = F.OBJECT_ID
            INNER JOIN SYS.INDEXES I ON F.REFERENCED_OBJECT_ID = I.OBJECT_ID AND F.KEY_INDEX_ID = I.INDEX_ID
        WHERE
            O1.OBJECT_ID = F.REFERENCED_OBJECT_ID
            AND O2.OBJECT_ID = F.PARENT_OBJECT_ID
            AND C1.OBJECT_ID = F.REFERENCED_OBJECT_ID
            AND C2.OBJECT_ID = F.PARENT_OBJECT_ID
            AND C1.COLUMN_ID = K.REFERENCED_COLUMN_ID
            AND C2.COLUMN_ID = K.PARENT_COLUMN_ID) sq ON sq.pkTableName = t1.name AND sq.pkColumnName = c1.name
ORDER BY
    t1.name,
    CASE WHEN pk.name IS NULL
        THEN CASE WHEN sq.fkName IS NULL THEN 3 ELSE 2 END
        ELSE 1
    END,
    c1.name''',

    # MYSQL
    # =================================================================================================
    'mysql': '''
SELECT
   c.table_name,
   c.column_name,
   CASE WHEN k.constraint_name = 'PRIMARY'
     THEN 'PK'
     ELSE
        CASE WHEN k.constraint_name LIKE 'FK%'
          THEN 'FK'
          ELSE NULL
        END
   END AS KEY_TYPE,
   c.data_type,
   c.character_maximum_length AS DATA_LENGTH,
   CASE WHEN UPPER(c.IS_NULLABLE)='YES'
      THEN 'Y'
      ELSE 'N'
   END AS NULLABLE,
   k.referenced_table_name AS FK_TABLE,
   k.referenced_column_name AS FK_COLUMN,
   CASE WHEN k.constraint_name = 'PRIMARY'
     THEN 'PK'
     ELSE
        CASE WHEN k.constraint_name LIKE 'FK%'
          THEN k.constraint_name
          ELSE NULL
        END
   END AS constraint_name,
   c.extra,
   s.cardinality
FROM
   information_schema.columns c
   LEFT JOIN information_schema.key_column_usage k ON
        k.constraint_schema=c.table_schema
        AND k.table_name = c.table_name
        AND k.column_name=c.column_name
    LEFT JOIN information_schema.statistics s ON
      s.table_schema = c.table_schema
      AND s.table_name = c.table_name
      AND s.column_name = c.column_name
WHERE
   c.table_schema = '@SCHEMA@'
ORDER BY
   c.table_name,
   CASE WHEN k.constraint_name = 'PRIMARY'
     THEN 1
     ELSE
        CASE WHEN k.constraint_name LIKE 'FK%'
          THEN 2
          ELSE 3
        END
   END,
   c.column_name''',

    # POSTGRESQL
    # =================================================================================================
    'postgresql': '''
SELECT
    c.table_name,
    c.column_name,
    CASE
        WHEN tc_pk.constraint_type IS NULL
        THEN CASE WHEN tc_fk.constraint_type IS NULL
                THEN NULL
                ELSE 'FK'
             END
        ELSE 'PK'
    END                        AS key_type,
    c.udt_name                 AS data_type,
    c.character_maximum_length AS data_length,
    c.is_nullable              AS nullable,
    ccu_fk.table_name          AS fk_table,
    ccu_fk.column_name         AS fk_column,
    COALESCE(tc_fk.constraint_name,tc_pk.constraint_name) AS constraint_name
FROM
    information_schema.tables t
    INNER JOIN information_schema.columns c ON c.table_name = t.table_name
        AND c.table_catalog = t.table_catalog
    LEFT JOIN information_schema.table_constraints tc_pk 
        INNER JOIN information_schema.key_column_usage kcu_pk ON kcu_pk.constraint_catalog = tc_pk.constraint_catalog
            AND kcu_pk.constraint_name = tc_pk.constraint_name 
    ON tc_pk.table_name=t.table_name
        AND tc_pk.constraint_catalog = t.table_catalog AND tc_pk.constraint_type = 'PRIMARY KEY'
        AND kcu_pk.column_name = c.column_name
    LEFT JOIN information_schema.table_constraints tc_fk 
        INNER JOIN information_schema.key_column_usage kcu_fk ON kcu_fk.constraint_catalog = tc_fk.constraint_catalog
            AND kcu_fk.constraint_name = tc_fk.constraint_name 
        INNER JOIN information_schema .constraint_column_usage AS ccu_fk ON ccu_fk.constraint_catalog = kcu_fk.constraint_catalog
            AND ccu_fk.constraint_name = kcu_fk.constraint_name
    ON tc_fk.table_name=t.table_name
        AND tc_fk.constraint_catalog = t.table_catalog AND tc_fk.constraint_type = 'FOREIGN KEY'
        AND kcu_fk.column_name = c.column_name
WHERE
    t.table_schema = 'public'
    AND t.table_type = 'BASE TABLE'
    AND t.table_catalog = '@SCHEMA@'
ORDER BY
    t.table_name,
    c.ordinal_position''',

    'sqlite': '''
SELECT tbl_name AS TABLE_NAME FROM sqlite_master where type='table' order by tbl_name'''
}

table_count_queries = {
    'oracle':     'SELECT COUNT(1) FROM USER_TABLES',
    'sqlserver':  'SELECT COUNT(1) FROM SYS.tables',
    'mysql':      "SELECT COUNT(DISTINCT table_name) FROM information_schema.columns WHERE table_schema = '@SCHEMA@'",
    'sqlite':     "SELECT COUNT(1) FROM sqlite_master WHERE type='table' ORDER BY tbl_name",
    'postgresql': '''
SELECT COUNT(DISTINCT table_nme) FROM information_schema.tables 
WHERE table_schema = 'public' AND table_type = 'BASE TABLE' AND table_catalog = '@SCHEMA@'
''',
}
