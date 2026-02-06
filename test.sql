-- =========================================================
-- dummy_seed_hackathon.sql
-- 목적: hackathon DB 초기화 + 추천 MVP 더미 데이터 시드
-- 대상 테이블: users, mentor_profiles, keyword, keyword_mapping
-- =========================================================

/*!40101 SET NAMES utf8mb4 */;
/*!40101 SET SQL_MODE = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION' */;

-- 0) DB 선택 (hackathon이 없다면 아래 CREATE DATABASE 주석 해제)
-- CREATE DATABASE IF NOT EXISTS hackathon
--   DEFAULT CHARACTER SET utf8mb4
--   DEFAULT COLLATE utf8mb4_unicode_ci;

USE hackathon;

-- 1) 초기화
SET FOREIGN_KEY_CHECKS = 0;
DROP TABLE IF EXISTS keyword_mapping;
DROP TABLE IF EXISTS mentor_profiles;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS keyword;
SET FOREIGN_KEY_CHECKS = 1;

-- 2) 테이블 생성
CREATE TABLE users (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(50) NOT NULL,
  role ENUM('MENTOR','MENTEE') NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE mentor_profiles (
  user_id BIGINT PRIMARY KEY,
  company VARCHAR(100) NOT NULL,
  price INT NOT NULL DEFAULT 0,
  mentoring_count INT NOT NULL DEFAULT 0,
  tech_stack VARCHAR(1000) NOT NULL DEFAULT '',
  CONSTRAINT fk_mp_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE keyword (
  id BIGINT PRIMARY KEY AUTO_INCREMENT,
  name VARCHAR(100) NOT NULL,
  UNIQUE KEY uk_keyword_name (name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE keyword_mapping (
  user_id BIGINT NOT NULL,
  keyword_id BIGINT NOT NULL,
  PRIMARY KEY (user_id, keyword_id),
  CONSTRAINT fk_km_user
    FOREIGN KEY (user_id) REFERENCES users(id)
    ON DELETE CASCADE ON UPDATE CASCADE,
  CONSTRAINT fk_km_keyword
    FOREIGN KEY (keyword_id) REFERENCES keyword(id)
    ON DELETE CASCADE ON UPDATE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 인덱스 (선택)
CREATE INDEX idx_users_role ON users(role);

-- 3) 키워드(토픽) 더미 데이터
-- 너 파이썬 TOPIC_RULES에 걸리게: n+1, index tuning, cache, tps, ci/cd, optimistic/pessimistic lock, 재고 차감 등
INSERT INTO keyword(name) VALUES
('N+1'),
('index tuning'),
('query tuning'),
('cache'),
('caching'),
('tps'),
('throughput'),
('latency'),
('ci/cd'),
('ci pipeline'),
('배포 자동화'),
('파이프라인 구축'),
('optimistic lock'),
('pessimistic lock'),
('락'),
('트랜잭션'),
('동시성 제어'),
('재고 차감'),
('inventory deduction'),
('stock deduction');

-- 4) 멘토/멘티 더미 유저
INSERT INTO users(name, role) VALUES
('민수', 'MENTOR'),
('지은', 'MENTOR'),
('현우', 'MENTOR'),
('서연', 'MENTOR'),
('도윤', 'MENTOR'),
('유나', 'MENTOR'),
('테스터', 'MENTEE');

-- 5) 멘토 프로필 더미
-- STACK_RULES에 걸리게: spring boot / postgresql / redis / github actions
INSERT INTO mentor_profiles(user_id, company, price, mentoring_count, tech_stack) VALUES
((SELECT id FROM users WHERE name='민수' AND role='MENTOR'), 'A사', 30000, 120, 'Spring Boot, PostgreSQL, Redis'),
((SELECT id FROM users WHERE name='지은' AND role='MENTOR'), 'B사', 25000, 60,  'Spring Boot, GitHub Actions'),
((SELECT id FROM users WHERE name='현우' AND role='MENTOR'), 'C사', 40000, 200, 'Spring Boot, PostgreSQL, Redis, GitHub Actions'),
((SELECT id FROM users WHERE name='서연' AND role='MENTOR'), 'D사', 20000, 15,  'Redis, Node.js'),
((SELECT id FROM users WHERE name='도윤' AND role='MENTOR'), 'E사', 35000, 90,  'PostgreSQL, Spring Boot'),
((SELECT id FROM users WHERE name='유나' AND role='MENTOR'), 'F사', 15000, 5,   'SpringBoot');

-- 6) 멘토-키워드 매핑 더미
-- 민수: N+1, index tuning, cache, tps
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id
FROM users u JOIN keyword k
WHERE u.name='민수' AND u.role='MENTOR'
  AND k.name IN ('N+1','index tuning','cache','tps');

-- 지은: ci/cd, 파이프라인 구축
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id
FROM users u JOIN keyword k
WHERE u.name='지은' AND u.role='MENTOR'
  AND k.name IN ('ci/cd','파이프라인 구축');

-- 현우: N+1, tps, optimistic lock, 재고 차감, index tuning, ci/cd
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id
FROM users u JOIN keyword k
WHERE u.name='현우' AND u.role='MENTOR'
  AND k.name IN ('N+1','tps','optimistic lock','재고 차감','index tuning','ci/cd');

-- 서연: cache, latency, throughput
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id
FROM users u JOIN keyword k
WHERE u.name='서연' AND u.role='MENTOR'
  AND k.name IN ('cache','latency','throughput');

-- 도윤: index tuning, query tuning, 트랜잭션
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id
FROM users u JOIN keyword k
WHERE u.name='도윤' AND u.role='MENTOR'
  AND k.name IN ('index tuning','query tuning','트랜잭션');

-- 유나: pessimistic lock, 재고 차감, 동시성 제어
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id
FROM users u JOIN keyword k
WHERE u.name='유나' AND u.role='MENTOR'
  AND k.name IN ('pessimistic lock','재고 차감','동시성 제어');

-- 7) 검증 쿼리
SELECT 'DB' AS what, DATABASE() AS value;

SHOW TABLES;

SELECT u.id, u.name, u.role, mp.company, mp.price, mp.mentoring_count, mp.tech_stack
FROM users u
LEFT JOIN mentor_profiles mp ON mp.user_id = u.id
ORDER BY u.id;

SELECT u.id, u.name,
       COALESCE(GROUP_CONCAT(k.name ORDER BY k.name SEPARATOR ', '), '') AS keywords
FROM users u
LEFT JOIN keyword_mapping km ON km.user_id = u.id
LEFT JOIN keyword k ON k.id = km.keyword_id
WHERE u.role='MENTOR'
GROUP BY u.id, u.name
ORDER BY u.id;
