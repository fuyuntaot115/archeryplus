CREATE OR ALTER  PROC [dbo].[UP_COPY_TABLE]
--[UP_COPY_TABLE] 'SQLVER','dbo','TBL_PERF',1
--DROP TABLE TBL_PERF_SQLVER,TBL_COPY_TABLE_HISTORY
--SELECT * FROm TBL_COPY_TABLE_HISTORY
	@TARGET NVARCHAR(256)
	,@schema_name NVARCHAR(256)
	, @TABLENAME NVARCHAR(256)
	, @exec int = 0
	, @FILTER NVARCHAR(256) = NULL
AS
SET NOCOUNT ON

--###########################################################################
--【必须修改】这里填写Linked Server对应的远端源数据库名称
DECLARE @RemoteDBName NVARCHAR(256) = N'{{SOURCE_DB}}';
--###########################################################################

DECLARE @STARTDATE DATETIME = DATEADD(HH,9,GETDATE())
DECLARE @DATE VARCHAR(100)
DECLARE @CREATETABLE NVARCHAR(MAX)
DECLARE @SQL NVARCHAR(MAX)
SET @DATE = CONVERT(VARCHAR(100), @STARTDATE, 121)
DECLARE @DBNAME NVARCHAR(256) = DB_NAME();
DECLARE @TARGETDBNAME NVARCHAR(256)
DECLARE @TARGETTABLENAME NVARCHAR(256) = @TARGET + '_' + @TABLENAME
DECLARE @TARGETFILTER NVARCHAR(256) = ''
IF @FILTER IS NOT NULL
	SET @TARGETFILTER = ' WHERE '+ @FILTER

IF OBJECT_ID('TBL_COPY_TABLE_HISTORY') IS NULL
BEGIN
	CREATE TABLE [dbo].[TBL_COPY_TABLE_HISTORY](
		[SOURCE] [nvarchar](256) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
		[TARGET] [nvarchar](256) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
		[TABLENAME] [nvarchar](256) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
		[TARGETTABLENAME] [nvarchar](256) COLLATE SQL_Latin1_General_CP1_CI_AS NULL,
		[REGDATE] [datetime] NULL,
		[DESC] [nvarchar](4000) COLLATE SQL_Latin1_General_CP1_CI_AS NULL
	) ON [PRIMARY]
	SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
	RAISERROR('--[%s || %s] There is no HistoryTable, Create table ',0,1,@DATE,'TBL_COPY_TABLE_HISTORY') WITH NOWAIT
END

----------------------------------------------
--GET TARGETDBNAME
--【修复】移除错误的OPENQUERY(@Q变量)写法，改用四部分名称
----------------------------------------------
DECLARE @TTARGETDBNAME TABLE (DBNAME NVARCHAR(256), [$ShardName] NVARCHAR(256))
DECLARE @_fourpart_dbname NVARCHAR(1024) = QUOTENAME(@TARGET)+N'.'+QUOTENAME(@RemoteDBName)+N'.sys.databases'

SET @SQL = N'SELECT name AS DBNAME FROM '+ @_fourpart_dbname + N' WHERE name = DB_NAME()'
INSERT INTO @TTARGETDBNAME
EXEC sp_executesql @SQL;

SELECT @TARGETDBNAME = DBNAME FROM @TTARGETDBNAME

----------------------------------------------
--GET COLUMNNAME
--【修复】四部分对象名直接查询Linked Server远端sys视图，变量全部保持原样
----------------------------------------------
DECLARE @C TABLE (CMD NVARCHAR(MAX), [$ShardName] NVARCHAR(256))
DECLARE @_fourpart_sys_prefix NVARCHAR(512) = QUOTENAME(@TARGET)+N'.'+QUOTENAME(@RemoteDBName)+N'.sys.'

SET @SQL=N'
SELECT ''('' + CHAR(13) + STUFF((
	SELECT CHAR(9) + '', ['' + c.name + ''] '' +
	    CASE WHEN c.is_computed = 1
	        THEN ''AS '' + cc.[definition]
	        ELSE UPPER(tp.name) +
	            CASE WHEN tp.name IN (''varchar'', ''char'', ''varbinary'', ''binary'', ''text'')
	                   THEN ''('' + CASE WHEN c.max_length = -1 THEN ''MAX'' ELSE CAST(c.max_length AS VARCHAR(5)) END + '')''
	                 WHEN tp.name IN (''nvarchar'', ''nchar'', ''ntext'')
	                   THEN ''('' + CASE WHEN c.max_length = -1 THEN ''MAX'' ELSE CAST(c.max_length / 2 AS VARCHAR(5)) END + '')''
	                 WHEN tp.name IN (''datetime2'', ''time2'', ''datetimeoffset'')
	                   THEN ''('' + CAST(c.scale AS VARCHAR(5)) + '')''
	                 WHEN tp.name = ''decimal''
	                   THEN ''('' + CAST(c.[precision] AS VARCHAR(5)) + '','' + CAST(c.scale AS VARCHAR(5)) + '')''
	                ELSE ''''
	            END +
	            CASE WHEN c.collation_name IS NOT NULL THEN '' COLLATE '' + c.collation_name ELSE '''' END +
	            CASE WHEN c.is_nullable = 1 THEN '' NULL'' ELSE '' NOT NULL'' END
				--+ CASE WHEN dc.[definition] IS NOT NULL THEN '' DEFAULT'' + dc.[definition] ELSE '''' END
	            --+CASE WHEN ic.is_identity = 1 THEN '' IDENTITY('' + CAST(ISNULL(ic.seed_value, ''0'') AS CHAR(1)) + '','' + CAST(ISNULL(ic.increment_value, ''1'') AS CHAR(1)) + '')'' ELSE '''' END
	    END + CHAR(13)
	FROM '+@_fourpart_sys_prefix+'tables t WITH (NOWAIT)
	INNER JOIN '+@_fourpart_sys_prefix+'columns c WITH (NOWAIT) ON t.[object_id] = c.[object_id]
	INNER JOIN '+@_fourpart_sys_prefix+'types tp WITH (NOWAIT) ON c.user_type_id = tp.user_type_id
	LEFT JOIN '+@_fourpart_sys_prefix+'computed_columns cc WITH (NOWAIT) ON c.[object_id] = cc.[object_id] AND c.column_id = cc.column_id
	LEFT JOIN '+@_fourpart_sys_prefix+'default_constraints dc WITH (NOWAIT) ON c.default_object_id != 0 AND c.[object_id] = dc.parent_object_id AND c.column_id = dc.parent_column_id
	LEFT JOIN '+@_fourpart_sys_prefix+'identity_columns ic WITH (NOWAIT) ON c.is_identity = 1 AND c.[object_id] = ic.[object_id] AND c.column_id = ic.column_id
	WHERE t.[name] = '''+REPLACE(@TABLENAME,'''','''''') +''' AND t.[schema_id] = SCHEMA_ID('''+REPLACE(@schema_name,'''','''''')+''')
	ORDER BY c.column_id
	FOR XML PATH(''''), TYPE).value(''.'', ''NVARCHAR(MAX)''), 1, 2, CHAR(9) + '' '')+'')''
'

INSERT INTO @C
EXEC sp_executesql @SQL
SELECT @CREATETABLE  = [CMD] FROM @C

SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
RAISERROR('--[%s || %s] START',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
IF @exec = 1
INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'START')

----------------------------------------------
----CHECK TARGET TABLE
----------------------------------------------
IF NOT EXISTS(SELECT name FROM sys.tables WHERE name = @TARGETTABLENAME)
BEGIN
	SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
	RAISERROR('--[%s || %s] There is no TargetTable, Create table ',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
	IF @exec = 1
	INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'There is no TargetTable, Create table')
	SELECT @SQL = ' CREATE TABLE '+'['+@schema_name+'].['+@TARGETTABLENAME+']'+
	+@CREATETABLE
	IF @exec = 1
	BEGIN
		EXEC (@SQL)
	END
	ELSE IF @exec = 0
	BEGIN
		PRINT @SQL
	END
END
ELSE
BEGIN
	SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
	RAISERROR('--[%s || %s] TARGET TABLE EXIST ',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
	IF @exec = 1
	INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'TARGET TABLE EXIST')
END

----------------------------------------------
----CHECK ROWCOUNT IN TARGETTABLE
----------------------------------------------
IF NOT EXISTS(SELECT OBJECT_NAME(id) TableName, rows FROM sys.sysindexes WHERE indid in (0,1) and id = OBJECT_ID(@TARGETTABLENAME) AND rowcnt = 0)
BEGIN
	IF EXISTS(SELECT name FROM sys.tables WHERE name = @TARGETTABLENAME)
	BEGIN
		SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
		RAISERROR('--[%s || %s] CHECK ROWCOUNT > 0',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
		SET @SQL= N'TRUNCATE TABLE ['+@schema_name+'].['+ @TARGETTABLENAME + ']'
		RAISERROR('--[%s || %s] %s',0,1,@DATE,@TARGETTABLENAME,@SQL) WITH NOWAIT
		IF @exec =1
			EXEC(@SQL)
		ELSE
			PRINT @SQL
		IF @exec = 1
		INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'CHECK ROWCOUNT > 0 ')
	END
END
ELSE
BEGIN
	SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
	RAISERROR('--[%s || %s] CHECK ROWCOUNT = 0',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
	IF @exec = 1
	INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'CHECK ROWCOUNT = 0')
END

--###########################################################################
--【删除Azure特有】DROP EXTERNAL TABLE / CREATE EXTERNAL TABLE 全部移除
--###########################################################################

----------------------------------------------
----TRANSFER DATA FROM REMOTE LINKED SERVER TO LOCAL
----------------------------------------------
DECLARE @_fourpart_remote_table NVARCHAR(1024)
SET @_fourpart_remote_table = QUOTENAME(@TARGET)+N'.'+QUOTENAME(@RemoteDBName)+N'.'+QUOTENAME(@schema_name)+N'.'+QUOTENAME(@TABLENAME)

SET @SQL = 'INSERT INTO ['+@schema_name+'].['+@TARGETTABLENAME+'] WITH (TABLOCKX)
	SELECT * FROM '+ @_fourpart_remote_table +' '+@TARGETFILTER+';'

IF @exec = 1
BEGIN
	EXEC SP_EXECUTESQL @SQL
	IF @@ERROR > 1
	BEGIN
		SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
		RAISERROR('--[%s || %s] TRANSFER DATA FAIL',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
		IF @exec = 1
		INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'TRANSFER DATA FAIL')
		RETURN
	END
	ELSE
	BEGIN
		SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
		RAISERROR('--[%s || %s] TRANSFER DATA OK',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
		IF @exec = 1
		INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'TRANSFER DATA OK')
	END
END
IF @exec = 0
BEGIN
	SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
	RAISERROR('--[%s || %s] TRANSFER DATA',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
	PRINT @SQL
END

----------------------------------------------
----CHECK ROW COUNT
----------------------------------------------
DECLARE @TROWCOUNT TABLE (DBNAME NVARCHAR(256), TABLENAME NVARCHAR(256), CNT BIGINT)
DECLARE @ROWCOUNT01 NVARCHAR(MAX) = N'SELECT DB_NAME(), '''+ @TABLENAME+''' , COUNT(*) FROM ['+@schema_name+'].['+@TARGETTABLENAME+'] WITH(NOLOCK)'
DECLARE @ROWCOUNT02 NVARCHAR(MAX)
SET @ROWCOUNT02 = N'SELECT '''+@TABLENAME+''' AS TABLENAME, COUNT(*) AS CNT FROM '+@_fourpart_remote_table + @TARGETFILTER

DECLARE @ROW01 VARCHAR(100)
DECLARE @ROW02 VARCHAR(100)

IF @exec = 1
BEGIN
	INSERT INTO @TROWCOUNT
	EXEC (@ROWCOUNT01)

	INSERT INTO @TROWCOUNT
	EXEC sp_executesql @ROWCOUNT02

	SELECT @ROW01 = CONVERT(VARCHAR(100), CNT) FROM @TROWCOUNT WHERE TABLENAME = @TABLENAME
	SELECT @ROW02 = CONVERT(VARCHAR(100), CNT) FROM @TROWCOUNT WHERE TABLENAME = @TARGETTABLENAME
	IF @ROW01=@ROW02
	BEGIN
		SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
		RAISERROR('--[%s || %s] CHECK ROWCOUNT - match (asis: %s tobe: %s)',0,1,@DATE,@TARGETTABLENAME,@ROW01,@ROW02) WITH NOWAIT
		IF @exec = 1
		INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'CHECK ROWCOUNT - match(asis: '+@ROW01+' tobe: '+@ROW02+')')
	END
	ELSE
	BEGIN
		SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
		RAISERROR('--[%s || %s] CHECK ROWCOUNT - NOT match (asis: %s tobe: %s)',0,1,@DATE,@TARGETTABLENAME,@ROW01,@ROW02) WITH NOWAIT
		IF @exec = 1
		INSERT INTO dbo.TBL_COPY_TABLE_HISTORY VALUES (@DBNAME, @TARGETDBNAME, @TABLENAME, @TARGETTABLENAME, DATEADD(HOUR, 9, GETDATE()), 'CHECK ROWCOUNT - NOT match')
	END
END
ELSE
BEGIN
	SET @DATE = CONVERT(CHAR(19),DATEADD(HOUR, 9, SYSUTCDATETIME()),121)
	RAISERROR('--[%s || %s] CHECK ROWCOUNT',0,1,@DATE,@TARGETTABLENAME) WITH NOWAIT
	PRINT @ROWCOUNT01
	PRINT @ROWCOUNT02
END

--###########################################################################
--【删除】原脚本末尾 DROP EXTERNAL TABLE 代码块；Linked Server无外部表对象
--###########################################################################

GO
--【删除原脚本末尾 sp_execute_remote 测试语句】
