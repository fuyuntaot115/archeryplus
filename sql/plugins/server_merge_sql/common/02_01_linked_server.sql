-- ============================================================================
-- 步骤 2-1：在目标库所在实例上创建外部数据源（Linked Server）
-- 说明：适用于自建 SQL Server / 具备 sysadmin 权限的实例
--      阿里云 RDS 请改用 sp_rds_add_linked_server（见文件末尾注释）
-- 变量：{{LINKED_SERVER}} {{SOURCE_HOST}} {{SOURCE_PORT}} {{SOURCE_DB}}
--       {{SOURCE_USER}} {{SOURCE_PASSWORD}}
-- ============================================================================

-- 已存在同名链接服务器时先删除（可重复执行）
IF EXISTS (SELECT 1 FROM sys.servers WHERE name = N'{{LINKED_SERVER}}')
    EXEC sp_dropserver @server = N'{{LINKED_SERVER}}', @droplogins = 'droplogins';
GO

-- 创建链接服务器
EXEC sp_addlinkedserver
    @server = N'{{LINKED_SERVER}}',
    @srvproduct = N'',
    @provider = N'MSOLEDBSQL',
    @datasrc = N'{{SOURCE_HOST}},{{SOURCE_PORT}}',
    @catalog = N'{{SOURCE_DB}}';
GO

-- 配置登录映射（SQL Server 身份验证）
EXEC sp_addlinkedsrvlogin
    @rmtsrvname = N'{{LINKED_SERVER}}',
    @useself = 'FALSE',
    @rmtuser = N'{{SOURCE_USER}}',
    @rmtpassword = N'{{SOURCE_PASSWORD}}';
GO

-- 配置链接服务器选项
EXEC sp_serveroption N'{{LINKED_SERVER}}', N'rpc', N'true';
EXEC sp_serveroption N'{{LINKED_SERVER}}', N'rpc out', N'true';
EXEC sp_serveroption N'{{LINKED_SERVER}}', N'data access', N'true';
EXEC sp_serveroption N'{{LINKED_SERVER}}', N'remote proc transaction promotion', N'true';
-- 两端排序规则一致时可开启（部分 SQL Server 版本已不支持该选项，默认关闭）
-- EXEC sp_serveroption N'{{LINKED_SERVER}}', N'collation compatible', N'true';

-- ----------------------------------------------------------------------------
-- 阿里云 RDS SQL Server 请改用以下写法（需先在 RDS 控制台创建链接服务器，或使用下面的存储过程）
-- DECLARE @link_server_options xml = N'
-- <rds_linked_server>
--     <config option="data access">true</config>
--     <config option="rpc">true</config>
--     <config option="rpc out">true</config>
-- </rds_linked_server>';
-- EXEC sp_rds_add_linked_server N'{{LINKED_SERVER}}', N'{{SOURCE_HOST}},{{SOURCE_PORT}}',
--     N'{{SOURCE_USER}}', N'{{SOURCE_PASSWORD}}', @link_server_options;
-- ----------------------------------------------------------------------------
