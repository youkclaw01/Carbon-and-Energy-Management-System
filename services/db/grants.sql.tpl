-- 서버에 디렉터리 읽기 권한(Graph)이 없어 이름 조회(FROM EXTERNAL PROVIDER) 대신 관리 ID의 clientId로 SID를 계산해 외부 사용자를 만든다.
IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name='{n}') BEGIN DECLARE @sid varbinary(16) = CAST(CAST('{cid}' AS uniqueidentifier) AS varbinary(16)); DECLARE @sql nvarchar(400) = N'CREATE USER [{n}] WITH SID = ' + CONVERT(nvarchar(100), @sid, 1) + N', TYPE = E'; EXEC(@sql); END
GO
{g}
GO
