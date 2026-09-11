INSERT INTO account_tb SELECT xa.* FROM account_tb a RIGHT OUTER JOIN XDS_account_tb xa ON a.AccountUID = xa.AccountUID WHERE a.AccountUID IS NULL;
INSERT INTO account_block_tb SELECT xa.* FROM account_block_tb a RIGHT OUTER JOIN XDS_account_block_tb xa ON a.AccountUID = xa.AccountUID WHERE a.AccountUID IS NULL;
INSERT INTO account_ex_tb SELECT xa.* FROM account_ex_tb a RIGHT OUTER JOIN	XDS_account_ex_tb xa ON a.AccountUID = xa.AccountUID WHERE a.AccountUID IS NULL;
INSERT INTO account_grade_tb SELECT xa.* FROM account_grade_tb a RIGHT OUTER JOIN XDS_account_grade_tb xa ON a.AccountUID = xa.AccountUID WHERE a.AccountUID IS NULL;
INSERT INTO mail_event_receipt_tb SELECT xa.* FROM mail_event_receipt_tb a RIGHT OUTER JOIN	XDS_mail_event_receipt_tb xa ON a.EventID = xa.EventID AND a.AccountUID = xa.AccountUID WHERE a.EventID IS NULL AND a.AccountUID IS NULL;
INSERT INTO nft_transfer_tb SELECT * FROM XDS_nft_transfer_tb;
INSERT INTO season_token_make_tb SELECT xa.* FROM season_token_make_tb a RIGHT OUTER JOIN XDS_season_token_make_tb xa ON a.AccountUID = xa.AccountUID WHERE a.AccountUID IS NULL;
INSERT INTO trade_register_tb SELECT * FROM XDS_trade_register_tb;
INSERT INTO trade_item_tb SELECT * FROM XDS_trade_item_tb;
INSERT INTO trade_item_option_tb SELECT a.* FROM XDS_trade_item_option_tb a LEFT JOIN XDS_trade_item_tb b ON a.ItemUID = b.ItemUID WHERE b.CharacterUID IS NOT NULL
INSERT INTO trade_item_lv_tb SELECT * FROM XDS_trade_item_lv_tb;
INSERT INTO trade_item_acquisition_path_tb SELECT * FROM XDS_trade_item_acquisition_path_tb;
ALTER TABLE world_character_tb DROP CONSTRAINT PK_world_Character_tb
INSERT INTO world_character_tb SELECT * FROM XDS_world_character_tb;
DELETE a FROM ( SELECT ROW_NUMBER() OVER ( PARTITION BY CharacterUID ORDER BY LoginTime DESC ) AS rn, * FROM world_character_tb ) a WHERE rn > 1
ALTER TABLE world_character_tb ADD CONSTRAINT PK_world_Character_tb PRIMARY KEY CLUSTERED ( CharacterUID )
INSERT INTO world_guild_tb SELECT * FROM XDS_world_guild_tb;
ALTER TABLE world_guild_member_tb DROP CONSTRAINT PK_world_guild_member_tb
INSERT INTO world_guild_member_tb SELECT * FROM XDS_world_guild_member_tb;
DELETE a FROM ( SELECT ROW_NUMBER() OVER ( PARTITION BY CharacterUID ORDER BY MemberJoinTime DESC ) AS rn, * FROM world_Guild_member_tb ) a WHERE rn > 1
ALTER TABLE world_guild_member_tb ADD CONSTRAINT PK_world_guild_member_tb PRIMARY KEY CLUSTERED ( CharacterUID )
