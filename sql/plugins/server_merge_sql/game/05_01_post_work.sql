-- ============================================================================
-- 说明：MergeMapping 建在 INDEX 库，本文件在 game/front 目标库执行，
--       因此下面使用跨库引用 [{{INDEX_DB}}].dbo.MergeMapping（INDEX 库由第一步选择自动带入）。
-- ============================================================================
UPDATE character_guild_tb SET OfficialGrade = 0;	-- 荤合己 包流 檬扁拳

UPDATE a SET	   WorldID = b.destination_world FROM character_tb							a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM guild_tb 								a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM dominion_wanted_tb					a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM money_dominion_storage_tb				a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM trade_register_tb						a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM trade_log_tb							a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM account_reward_tb						a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM money_account_tb						a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM collection_item_account_complate_tb	a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM collection_item_account_tb			a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET	   WorldID = b.destination_world FROM productbuycnt_account_tb 				a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON		 a.WorldID = b.source_world
UPDATE a SET TargetWorldID = b.destination_world FROM guild_command_mark_tb					a INNER JOIN [{{INDEX_DB}}].dbo.MergeMapping b ON a.TargetWorldID = b.source_world
