-- ============================================================================
-- 说明：MergeMapping 建在 INDEX 库，本文件在 game/front 目标库执行，
--       因此下面使用跨库引用 [{{INDEX_DB}}].dbo.MergeMapping（INDEX 库由第一步选择自动带入）。
-- ============================================================================
UPDATE a SET	   a.WorldId = b.destination_world FROM trade_register_tb	a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldId = b.source_world
UPDATE a SET	   a.WorldID = b.destination_world FROM world_character_tb	a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET a.CreateWorldID = b.destination_world FROM world_guild_tb		a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON a.CreateWorldID = b.source_world

DELETE a FROM world_db_tb a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON	      a.WorldID = b.source_world
DELETE a FROM		db_tb a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON a.DBConnectionName = b.source_db
DELETE a FROM	 world_tb a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON	      a.WorldID = b.source_world
