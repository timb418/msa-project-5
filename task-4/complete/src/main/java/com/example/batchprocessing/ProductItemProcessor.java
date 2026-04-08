package com.example.batchprocessing;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import org.springframework.batch.item.ItemProcessor;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.jdbc.core.DataClassRowMapper;
import org.springframework.jdbc.core.namedparam.NamedParameterJdbcTemplate;
import org.springframework.stereotype.Component;

import java.util.Map;
import java.util.Optional;

@Component
public class ProductItemProcessor implements ItemProcessor<Product, Product> {

	private static final Logger log = LoggerFactory.getLogger(ProductItemProcessor.class);

	@Autowired
	private NamedParameterJdbcTemplate jdbcTemplate;

    @Override
	public Product process(final Product product) {
		Optional<String> loyalityData = jdbcTemplate
				.query(
						"SELECT * FROM loyality_data WHERE productSku = :sku",
						Map.of("sku", product.productSku()),
						new DataClassRowMapper<>(Loyality.class)
				)
				.stream().findFirst().map(Loyality::loyalityData);

		Product transformed = loyalityData
				.map(data -> new Product(product.productId(), product.productSku(), product.productName(), product.productAmount(), data))
				.orElse(product);

		log.info("Transforming ({}) into ({})", product, transformed);

		return transformed;
	}

}
