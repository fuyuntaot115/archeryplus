UPDATE trade_register_tb SET TradeUid = (TradeUid*100000000000)+WorldID FROM trade_register_tb WHERE RegionTrade = 0
DELETE a FROM trade_log_tb a INNER JOIN trade_register_tb b ON a.TradeUid = b.TradeUid AND RegionTrade = 0
DELETE a FROM guild_history_param_tb a LEFT OUTER JOIN guild_history_tb b ON a.HistoryUID = b.HistoryUID WHERE b.GuildUID IS NULL
DELETE a FROM guild_history_money_tb a LEFT OUTER JOIN guild_history_tb b ON a.HistoryUID = b.HistoryUID WHERE b.GuildUID IS NULL
DELETE a FROM equip_costume_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM equip_costume_tb a LEFT OUTER JOIN costume_tb b ON a.CharacterUID = b.CharacterUID AND a.CostumeIdx = b.CostumeIdx WHERE b.CharacterUID IS NULL
DELETE a FROM costume_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM force_blood_tb a LEFT OUTER JOIN force_tb b ON a.CharacterUID = b.CharacterUID AND a.ForceIdx = b.ForceIdx WHERE b.CharacterUID IS NULL
DELETE a FROM customize_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM productbuycnt_character_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM equip_costumehide_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM equip_item_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM character_guild_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM achievement_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
DELETE a FROM battle_pass_reward_tb a LEFT OUTER JOIN character_tb b ON a.CharacterUID = b.CharacterUID WHERE b.CharacterUID IS NULL
