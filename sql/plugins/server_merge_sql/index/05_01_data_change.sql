UPDATE a SET a.World_ID = b.destination_world FROM character_index_tb	a INNER JOIN MergeMapping b ON a.World_ID = b.source_world
UPDATE a SET  a.WorldID = b.destination_world FROM rank_info_tb			a INNER JOIN MergeMapping b ON  a.WorldID = b.source_world
UPDATE world_info_tb SET WorldName = 'ASIA334', WorldID = 934										WHERE WorldName = 'ASIA341'
UPDATE world_info_tb SET WorldName = 'ASIA034', WorldID = 834, WorldGroup = 1, RegionGroupDB = 1	WHERE WorldName = 'ASIA373'
DELETE FROM world_info_tb WHERE WorldGroup IN ( 12, 15, 31 )

INSERT INTO world_info_tb
SELECT 311,31,1,31,0,0,0,  'ASIA311',3 UNION ALL
SELECT 312,31,1,31,0,0,0,  'ASIA312',3 UNION ALL
SELECT 313,31,1,31,0,0,0,  'ASIA313',3 UNION ALL
SELECT 252, 6,6, 6,0,0,0,'INMENA252',3 UNION ALL
SELECT 652, 3,3, 3,0,0,0,	 'EU652',3 UNION ALL
SELECT 752,15,5,15,0,0,0,	 'SA752',3 UNION ALL
SELECT 552,12,2,12,0,0,0,	 'NA552',3
