-- =========================================================
-- dummy_seed_hackathon.sql (멘토 15명 / 총 30명 버전)
-- =========================================================

/*!40101 SET NAMES utf8mb4 */;
/*!40101 SET SQL_MODE = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION' */;

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

CREATE INDEX idx_users_role ON users(role);

-- 3) 키워드(토픽)
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

-- 4) 유저 30명 (멘토 15 / 멘티 15)
INSERT INTO users(name, role) VALUES
-- mentors (15)
('민수', 'MENTOR'),
('지은', 'MENTOR'),
('현우', 'MENTOR'),
('서연', 'MENTOR'),
('도윤', 'MENTOR'),
('유나', 'MENTOR'),
('태현', 'MENTOR'),
('서우', 'MENTOR'),
('지훈', 'MENTOR'),
('예성', 'MENTOR'),
('나영', 'MENTOR'),
('현진', 'MENTOR'),
('주원', 'MENTOR'),
('하율', 'MENTOR'),
('동혁', 'MENTOR'),

-- mentees (15)
('테스터', 'MENTEE'),
('민지', 'MENTEE'),
('준호', 'MENTEE'),
('수빈', 'MENTEE'),
('지후', 'MENTEE'),
('예린', 'MENTEE'),
('태윤', 'MENTEE'),
('하은', 'MENTEE'),
('정우', 'MENTEE'),
('다은', 'MENTEE'),
('승민', 'MENTEE'),
('소연', 'MENTEE'),
('시우', 'MENTEE'),
('채원', 'MENTEE'),
('유진', 'MENTEE');

-- 5) 멘토 프로필 (15명)
INSERT INTO mentor_profiles(user_id, company, price, mentoring_count, tech_stack) VALUES
-- 기존 6
((SELECT id FROM users WHERE name='민수' AND role='MENTOR'), 'A사', 30000, 120, 'Spring Boot, PostgreSQL, Redis'),
((SELECT id FROM users WHERE name='지은' AND role='MENTOR'), 'B사', 25000, 60,  'Spring Boot, GitHub Actions'),
((SELECT id FROM users WHERE name='현우' AND role='MENTOR'), 'C사', 40000, 200, 'Spring Boot, PostgreSQL, Redis, GitHub Actions'),
((SELECT id FROM users WHERE name='서연' AND role='MENTOR'), 'D사', 20000, 15,  'Redis, Node.js'),
((SELECT id FROM users WHERE name='도윤' AND role='MENTOR'), 'E사', 35000, 90,  'PostgreSQL, Spring Boot'),
((SELECT id FROM users WHERE name='유나' AND role='MENTOR'), 'F사', 15000, 5,   'SpringBoot'),

-- 추가 9
((SELECT id FROM users WHERE name='태현' AND role='MENTOR'), 'G사', 28000, 40,  'Spring Boot, PostgreSQL'),
((SELECT id FROM users WHERE name='서우' AND role='MENTOR'), 'H사', 22000, 25,  'Redis, Spring Boot'),
((SELECT id FROM users WHERE name='지훈' AND role='MENTOR'), 'I사', 45000, 180, 'PostgreSQL, Redis, GitHub Actions'),
((SELECT id FROM users WHERE name='예성' AND role='MENTOR'), 'J사', 32000, 70,  'Spring Boot, GitHub Actions, Redis'),
((SELECT id FROM users WHERE name='나영' AND role='MENTOR'), 'K사', 18000, 12,  'PostgreSQL, Node.js'),
((SELECT id FROM users WHERE name='현진' AND role='MENTOR'), 'L사', 38000, 110, 'Spring Boot, PostgreSQL, GitHub Actions'),
((SELECT id FROM users WHERE name='주원' AND role='MENTOR'), 'M사', 26000, 55,  'Redis, GitHub Actions'),
((SELECT id FROM users WHERE name='하율' AND role='MENTOR'), 'N사', 41000, 160, 'Spring Boot, PostgreSQL, Redis'),
((SELECT id FROM users WHERE name='동혁' AND role='MENTOR'), 'O사', 24000, 30,  'Spring Boot, PostgreSQL, Redis, GitHub Actions');

-- 6) 멘토-키워드 매핑 (15명 전부 넣기)

-- 기존 6명 매핑 유지
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='민수' AND u.role='MENTOR'
  AND k.name IN ('N+1','index tuning','cache','tps');

INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='지은' AND u.role='MENTOR'
  AND k.name IN ('ci/cd','파이프라인 구축');

INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='현우' AND u.role='MENTOR'
  AND k.name IN ('N+1','tps','optimistic lock','재고 차감','index tuning','ci/cd');

INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='서연' AND u.role='MENTOR'
  AND k.name IN ('cache','latency','throughput');

INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='도윤' AND u.role='MENTOR'
  AND k.name IN ('index tuning','query tuning','트랜잭션');

INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='유나' AND u.role='MENTOR'
  AND k.name IN ('pessimistic lock','재고 차감','동시성 제어');

-- 추가 9명 매핑
-- 태현: query tuning, latency, index tuning
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='태현' AND u.role='MENTOR'
  AND k.name IN ('query tuning','latency','index tuning');

-- 서우: cache, caching, throughput
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='서우' AND u.role='MENTOR'
  AND k.name IN ('cache','caching','throughput');

-- 지훈: ci/cd, ci pipeline, 배포 자동화
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='지훈' AND u.role='MENTOR'
  AND k.name IN ('ci/cd','ci pipeline','배포 자동화');

-- 예성: N+1, cache, throughput, latency
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='예성' AND u.role='MENTOR'
  AND k.name IN ('N+1','cache','throughput','latency');

-- 나영: 트랜잭션, 락, 동시성 제어
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='나영' AND u.role='MENTOR'
  AND k.name IN ('트랜잭션','락','동시성 제어');

-- 현진: index tuning, query tuning, ci/cd
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='현진' AND u.role='MENTOR'
  AND k.name IN ('index tuning','query tuning','ci/cd');

-- 주원: 파이프라인 구축, ci pipeline, 배포 자동화
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='주원' AND u.role='MENTOR'
  AND k.name IN ('파이프라인 구축','ci pipeline','배포 자동화');

-- 하율: optimistic lock, 재고 차감, tps
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='하율' AND u.role='MENTOR'
  AND k.name IN ('optimistic lock','재고 차감','tps');

-- 동혁: pessimistic lock, stock deduction, inventory deduction
INSERT INTO keyword_mapping(user_id, keyword_id)
SELECT u.id, k.id FROM users u JOIN keyword k
WHERE u.name='동혁' AND u.role='MENTOR'
  AND k.name IN ('pessimistic lock','stock deduction','inventory deduction');

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
