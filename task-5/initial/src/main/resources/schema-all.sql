CREATE TABLE products  (
    productId BIGINT NOT NULL PRIMARY KEY,
    productSku BIGINT NOT NULL UNIQUE,
    productName VARCHAR(20),
    productAmount BIGINT,
    productData VARCHAR(120)
);

CREATE TABLE loyality_data  (
    productSku BIGINT NOT NULL PRIMARY KEY,
    loyalityData VARCHAR(120)
);