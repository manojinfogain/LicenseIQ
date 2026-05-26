-- Update Claude AI purchased/contracted seat count from 130 to 150.
UPDATE pc
SET contracted_seats = 150
FROM platform_contracts pc
INNER JOIN platforms p ON p.id = pc.platform_id
WHERE p.name = N'Claude AI'
  AND (pc.contracted_seats = 130 OR pc.contracted_seats IS NULL);
