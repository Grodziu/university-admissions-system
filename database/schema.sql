--
-- PostgreSQL database dump
--

\restrict roMXHST3aGuGAQ89bNA3xt39nFwP0X976aXVNy0IVslGw9gbkzKKQ8Vf8G6AyY9

-- Dumped from database version 17.12
-- Dumped by pg_dump version 17.12

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pk_application_audit(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_application_audit() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
DECLARE b jsonb; a jsonb;
BEGIN
  IF TG_OP <> 'INSERT' THEN
    b := jsonb_build_object('status',OLD.status,'revision',OLD.revision,'offer',OLD.offer_id,'round',OLD.round_id,'payment_approved',OLD.payment_approved);
    UPDATE pk_offer_stats SET applications=applications-1,
      verified=verified-(CASE WHEN OLD.status IN ('verified','qualified','waitlist','confirmed') THEN 1 ELSE 0 END),
      confirmed=confirmed-(CASE WHEN OLD.status='confirmed' THEN 1 ELSE 0 END) WHERE offer_id=OLD.offer_id;
  END IF;
  IF TG_OP <> 'DELETE' THEN
    a := jsonb_build_object('status',NEW.status,'revision',NEW.revision,'offer',NEW.offer_id,'round',NEW.round_id,'payment_approved',NEW.payment_approved);
    INSERT INTO pk_offer_stats(offer_id,applications,verified,confirmed)
    VALUES(NEW.offer_id,1,CASE WHEN NEW.status IN ('verified','qualified','waitlist','confirmed') THEN 1 ELSE 0 END,CASE WHEN NEW.status='confirmed' THEN 1 ELSE 0 END)
    ON CONFLICT(offer_id) DO UPDATE SET applications=pk_offer_stats.applications+1,
      verified=pk_offer_stats.verified+EXCLUDED.verified, confirmed=pk_offer_stats.confirmed+EXCLUDED.confirmed;
  END IF;
  INSERT INTO pk_row_audit(operation,application_id,before_state,after_state)
    VALUES(TG_OP,COALESCE(NEW.id,OLD.id),b,a);
  RETURN COALESCE(NEW,OLD);
END $$;


--
-- Name: pk_application_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_application_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
DECLARE o admissions_offer; r admissions_round;
BEGIN
  SELECT * INTO STRICT o FROM admissions_offer WHERE id=NEW.offer_id;
  SELECT * INTO STRICT r FROM admissions_round WHERE id=NEW.round_id;
  IF o.campaign_id<>r.campaign_id OR o.degree<>r.degree THEN
    RAISE EXCEPTION 'Application round must belong to its offer degree and campaign';
  END IF;
  IF NEW.payment_approved AND (NEW.payment_amount IS NULL OR NEW.payment_amount<>o.fee) THEN
    RAISE EXCEPTION 'Approved payment must equal the offer fee';
  END IF;
  RETURN NEW;
END $$;


--
-- Name: pk_application_statement_audit(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_application_statement_audit() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
  INSERT INTO pk_statement_audit(operation,affected_rows) SELECT TG_OP,count(*) FROM changed;
  RETURN NULL;
END $$;


--
-- Name: pk_contact_write(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_contact_write() RETURNS trigger
    LANGUAGE plpgsql SECURITY DEFINER
    SET search_path TO 'public', 'pg_temp'
    AS $$
BEGIN
 IF TG_OP='DELETE' THEN
   DELETE FROM admissions_candidatephone WHERE user_id=OLD.user_id;
   DELETE FROM admissions_candidateportfolio WHERE user_id=OLD.user_id;
   DELETE FROM admissions_candidatenotificationaddress WHERE user_id=OLD.user_id;
   DELETE FROM admissions_contactanchor WHERE user_id=OLD.user_id;
   RETURN OLD;
 END IF;
 IF TG_OP='INSERT' THEN
   INSERT INTO admissions_contactanchor(user_id) VALUES(NEW.user_id);
 ELSE
   IF NEW.user_id IS DISTINCT FROM OLD.user_id THEN
     RAISE EXCEPTION 'The contact owner cannot be changed' USING ERRCODE='23514';
   END IF;
   PERFORM 1 FROM admissions_contactanchor WHERE user_id=OLD.user_id FOR UPDATE;
 END IF;
 IF TG_OP='INSERT' OR NEW.phone IS DISTINCT FROM OLD.phone THEN
 IF NEW.phone = '' THEN
   DELETE FROM admissions_candidatephone WHERE user_id=NEW.user_id;
 ELSE
   INSERT INTO admissions_candidatephone(user_id,value) VALUES(NEW.user_id,NEW.phone)
   ON CONFLICT(user_id) DO UPDATE SET value=EXCLUDED.value;
 END IF;
 END IF;
 IF TG_OP='INSERT' OR NEW.portfolio_url IS DISTINCT FROM OLD.portfolio_url THEN
 IF NEW.portfolio_url = '' THEN
   DELETE FROM admissions_candidateportfolio WHERE user_id=NEW.user_id;
 ELSE
   INSERT INTO admissions_candidateportfolio(user_id,value) VALUES(NEW.user_id,NEW.portfolio_url)
   ON CONFLICT(user_id) DO UPDATE SET value=EXCLUDED.value;
 END IF;
 END IF;
 IF TG_OP='INSERT' OR NEW.notification_email IS DISTINCT FROM OLD.notification_email THEN
 IF NEW.notification_email = '' THEN
   DELETE FROM admissions_candidatenotificationaddress WHERE user_id=NEW.user_id;
 ELSE
   INSERT INTO admissions_candidatenotificationaddress(user_id,value) VALUES(NEW.user_id,NEW.notification_email)
   ON CONFLICT(user_id) DO UPDATE SET value=EXCLUDED.value;
 END IF;
 END IF;
 RETURN NEW;
END $$;


--
-- Name: pk_immutable_publication(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_immutable_publication() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN RAISE EXCEPTION 'Published admission records are immutable; create a new version'; END $$;


--
-- Name: pk_oath_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_oath_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND OLD.sworn_at IS NOT NULL AND
    (NEW.sworn_at IS DISTINCT FROM OLD.sworn_at OR NEW.student_number IS DISTINCT FROM OLD.student_number
     OR NEW.oath_photo_id IS DISTINCT FROM OLD.oath_photo_id) THEN
    RAISE EXCEPTION 'An accepted oath and its photo are immutable';
  END IF;
  IF NEW.sworn_at IS NOT NULL AND NOT EXISTS (
     SELECT 1 FROM admissions_offer o JOIN admissions_campaign c ON c.id=o.campaign_id
     JOIN admissions_profilephoto p ON p.id=NEW.oath_photo_id
     WHERE o.id=NEW.offer_id AND c.closed AND o.state='launched' AND NEW.status='confirmed'
       AND p.user_id=NEW.candidate_id AND p.approved_at IS NOT NULL AND NEW.student_number IS NOT NULL
  ) THEN
    RAISE EXCEPTION 'Oath requires a confirmed place and the candidate''s approved profile photo';
  END IF;
  RETURN NEW;
END $$;


--
-- Name: pk_photo_freeze(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_photo_freeze() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF NEW.kind='photo' AND EXISTS (SELECT 1 FROM admissions_application WHERE id=NEW.application_id AND sworn_at IS NOT NULL) THEN
    RAISE EXCEPTION 'Photo is frozen after the oath';
  END IF;
  RETURN NEW;
END $$;


--
-- Name: pk_profile_photo_guard(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_profile_photo_guard() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  IF (NEW.user_id, NEW.version, NEW.file, NEW.sha256) IS DISTINCT FROM
     (OLD.user_id, OLD.version, OLD.file, OLD.sha256)
     OR (OLD.approved_at IS NOT NULL AND
         (NEW.approved_at, NEW.approved_by_id) IS DISTINCT FROM (OLD.approved_at, OLD.approved_by_id)) THEN
    RAISE EXCEPTION 'An existing profile photo and its approval cannot be replaced';
  END IF;
  RETURN NEW;
END $$;


--
-- Name: pk_reconcile_offer_stats(); Type: PROCEDURE; Schema: public; Owner: -
--

CREATE PROCEDURE public.pk_reconcile_offer_stats()
    LANGUAGE sql
    AS $$
  INSERT INTO pk_offer_stats(offer_id,applications,verified,confirmed)
  SELECT o.id,count(a.id), count(a.id) FILTER (WHERE a.status IN ('verified','qualified','waitlist','confirmed')),
         count(a.id) FILTER (WHERE a.status='confirmed')
  FROM admissions_offer o LEFT JOIN admissions_application a ON a.offer_id=o.id GROUP BY o.id
  ON CONFLICT(offer_id) DO UPDATE SET applications=EXCLUDED.applications,verified=EXCLUDED.verified,confirmed=EXCLUDED.confirmed;
$$;


--
-- Name: pk_wr(numeric, numeric, numeric, numeric); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.pk_wr(m numeric, p1 numeric, p2 numeric, bonus numeric) RETURNS numeric
    LANGUAGE plpgsql IMMUTABLE STRICT
    AS $$
BEGIN
  IF NOT (m BETWEEN 0 AND 100 AND p1 BETWEEN 0 AND 100 AND p2 BETWEEN 0 AND 100
          AND bonus BETWEEN 0 AND 50 AND bonus = trunc(bonus)) THEN
    RAISE EXCEPTION 'Invalid WR components';
  END IF;
  RETURN LEAST(1000::numeric, 2*m + 6*p1 + 2*p2 + bonus);
END $$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: admissions_academicaverage; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_academicaverage (
    user_id bigint NOT NULL,
    value numeric(4,2) NOT NULL,
    CONSTRAINT average_2_5 CHECK (((value >= (2)::numeric) AND (value <= (5)::numeric)))
);


--
-- Name: admissions_allowedprofession; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_allowedprofession (
    id bigint NOT NULL,
    name character varying(80) NOT NULL,
    offer_id bigint NOT NULL
);


--
-- Name: admissions_allowedprofession_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_allowedprofession ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_allowedprofession_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_allowedsubject; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_allowedsubject (
    id bigint NOT NULL,
    subject character varying(80) NOT NULL,
    offer_id bigint NOT NULL
);


--
-- Name: admissions_allowedsubject_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_allowedsubject ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_allowedsubject_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_application; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_application (
    id bigint NOT NULL,
    public_id uuid NOT NULL,
    status character varying(12) NOT NULL,
    created_at timestamp with time zone NOT NULL,
    submitted_at timestamp with time zone,
    revision integer NOT NULL,
    input_snapshot jsonb NOT NULL,
    feedback text NOT NULL,
    bonus_claimed boolean NOT NULL,
    bonus_approved boolean NOT NULL,
    portfolio_grade character varying(12) NOT NULL,
    payment_approved boolean NOT NULL,
    payment_amount numeric(8,2),
    portfolio_url character varying(500) NOT NULL,
    candidate_id bigint NOT NULL,
    reviewed_by_id bigint,
    offer_id bigint NOT NULL,
    round_id bigint NOT NULL,
    bonus_category character varying(40) NOT NULL,
    bonus_points smallint NOT NULL,
    student_number character varying(40),
    sworn_at timestamp with time zone,
    oath_photo_id bigint,
    CONSTRAINT admissions_application_bonus_points_check CHECK ((bonus_points >= 0)),
    CONSTRAINT admissions_application_revision_check CHECK ((revision >= 0)),
    CONSTRAINT bonus_0_50 CHECK ((bonus_points <= 50))
);


--
-- Name: admissions_application_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_application ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_application_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_auditevent; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_auditevent (
    id bigint NOT NULL,
    action character varying(80) NOT NULL,
    entity character varying(120) NOT NULL,
    details jsonb NOT NULL,
    created_at timestamp with time zone NOT NULL,
    actor_id bigint
);


--
-- Name: admissions_auditevent_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_auditevent ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_auditevent_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_campaign; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_campaign (
    id bigint NOT NULL,
    name character varying(100) NOT NULL,
    start timestamp with time zone NOT NULL,
    "end" timestamp with time zone NOT NULL,
    demo_clock timestamp with time zone,
    closed boolean NOT NULL,
    demo_scenario character varying(40) NOT NULL
);


--
-- Name: admissions_campaign_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_campaign ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_campaign_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_candidatenotificationaddress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_candidatenotificationaddress (
    user_id bigint NOT NULL,
    value character varying(254) NOT NULL,
    CONSTRAINT notification_fact_nonempty CHECK ((NOT ((value)::text = ''::text)))
);


--
-- Name: admissions_candidatephone; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_candidatephone (
    user_id bigint NOT NULL,
    value character varying(30) NOT NULL,
    CONSTRAINT phone_fact_nonempty CHECK ((NOT ((value)::text = ''::text)))
);


--
-- Name: admissions_candidateportfolio; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_candidateportfolio (
    user_id bigint NOT NULL,
    value character varying(500) NOT NULL,
    CONSTRAINT portfolio_fact_nonempty CHECK ((NOT ((value)::text = ''::text)))
);


--
-- Name: admissions_contactanchor; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_contactanchor (
    user_id bigint NOT NULL
);


--
-- Name: admissions_candidatecontact; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.admissions_candidatecontact AS
 SELECT user_id,
    (COALESCE(( SELECT admissions_candidatephone.value
           FROM public.admissions_candidatephone
          WHERE (admissions_candidatephone.user_id = a.user_id)), ''::character varying))::character varying(30) AS phone,
    (COALESCE(( SELECT admissions_candidateportfolio.value
           FROM public.admissions_candidateportfolio
          WHERE (admissions_candidateportfolio.user_id = a.user_id)), ''::character varying))::character varying(500) AS portfolio_url,
    (COALESCE(( SELECT admissions_candidatenotificationaddress.value
           FROM public.admissions_candidatenotificationaddress
          WHERE (admissions_candidatenotificationaddress.user_id = a.user_id)), ''::character varying))::character varying(254) AS notification_email
   FROM public.admissions_contactanchor a;


--
-- Name: admissions_candidateidentity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_candidateidentity (
    user_id bigint NOT NULL,
    pesel character varying(11) NOT NULL,
    CONSTRAINT pesel_digits CHECK (((pesel)::text ~ '^[0-9]{11}$'::text))
);


--
-- Name: admissions_diploma; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_diploma (
    user_id bigint NOT NULL,
    title character varying(120) NOT NULL
);


--
-- Name: admissions_document; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_document (
    id bigint NOT NULL,
    kind character varying(16) NOT NULL,
    revision integer NOT NULL,
    file character varying(100) NOT NULL,
    original_name character varying(200) NOT NULL,
    sha256 character varying(64) NOT NULL,
    uploaded_at timestamp with time zone NOT NULL,
    application_id bigint NOT NULL,
    reused_from_id bigint,
    profile_source_id bigint,
    CONSTRAINT admissions_document_revision_check CHECK ((revision >= 0))
);


--
-- Name: admissions_document_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_document ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_document_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_dormitory; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_dormitory (
    code character varying(4) NOT NULL,
    name character varying(50) NOT NULL,
    address character varying(150) NOT NULL,
    description text NOT NULL,
    seats smallint NOT NULL,
    latitude numeric(9,6) NOT NULL,
    longitude numeric(9,6) NOT NULL,
    CONSTRAINT admissions_dormitory_seats_check CHECK ((seats >= 0)),
    CONSTRAINT dorm_positive_seats CHECK ((seats > 0))
);


--
-- Name: admissions_emaildelivery; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_emaildelivery (
    id bigint NOT NULL,
    recipient character varying(254) NOT NULL,
    state character varying(10) NOT NULL,
    attempts smallint NOT NULL,
    available_at timestamp with time zone NOT NULL,
    notification_id bigint NOT NULL,
    CONSTRAINT admissions_emaildelivery_attempts_check CHECK ((attempts >= 0))
);


--
-- Name: admissions_emaildelivery_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_emaildelivery ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_emaildelivery_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_examresult; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_examresult (
    id bigint NOT NULL,
    subject character varying(80) NOT NULL,
    level character varying(12) NOT NULL,
    value numeric(5,2) NOT NULL,
    user_id bigint NOT NULL,
    CONSTRAINT exam_0_100 CHECK (((value >= (0)::numeric) AND (value <= (100)::numeric)))
);


--
-- Name: admissions_examresult_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_examresult ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_examresult_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_faculty; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_faculty (
    id bigint NOT NULL,
    code character varying(12) NOT NULL,
    name character varying(150) NOT NULL,
    color character varying(7) NOT NULL
);


--
-- Name: admissions_faculty_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_faculty ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_faculty_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_housingapplication; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_housingapplication (
    id bigint NOT NULL,
    status character varying(12) NOT NULL,
    distance_km numeric(7,2) NOT NULL,
    score_index numeric(6,2),
    submitted_at timestamp with time zone NOT NULL,
    allocated_id character varying(4),
    campaign_id bigint NOT NULL,
    candidate_id bigint NOT NULL,
    enrollment_id bigint,
    preferred_id character varying(4) NOT NULL,
    CONSTRAINT housing_allocation_status CHECK ((((allocated_id IS NOT NULL) AND (enrollment_id IS NOT NULL) AND ((status)::text = 'awarded'::text)) OR ((NOT ((status)::text = 'awarded'::text)) AND (allocated_id IS NULL)))),
    CONSTRAINT housing_distance_positive CHECK ((distance_km >= (0)::numeric))
);


--
-- Name: admissions_housingapplication_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_housingapplication ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_housingapplication_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_notification; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_notification (
    id bigint NOT NULL,
    title character varying(150) NOT NULL,
    message text NOT NULL,
    created_at timestamp with time zone NOT NULL,
    read boolean NOT NULL,
    user_id bigint NOT NULL
);


--
-- Name: admissions_notification_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_notification ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_notification_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_offer; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_offer (
    id bigint NOT NULL,
    degree character varying(2) NOT NULL,
    mode character varying(2) NOT NULL,
    capacity integer NOT NULL,
    minimum integer NOT NULL,
    fee numeric(8,2) NOT NULL,
    portfolio_required boolean NOT NULL,
    portfolio_bonus boolean NOT NULL,
    state character varying(12) NOT NULL,
    rule_version character varying(30) NOT NULL,
    campaign_id bigint NOT NULL,
    program_id bigint NOT NULL,
    photo_required boolean NOT NULL,
    tuition_per_semester numeric(8,2),
    CONSTRAINT admissions_offer_capacity_check CHECK ((capacity >= 0)),
    CONSTRAINT admissions_offer_minimum_check CHECK ((minimum >= 0)),
    CONSTRAINT offer_limits CHECK (((capacity >= minimum) AND (minimum > 0) AND (fee > (0)::numeric))),
    CONSTRAINT positive_semester_tuition CHECK (((tuition_per_semester IS NULL) OR (tuition_per_semester > (0)::numeric))),
    CONSTRAINT postgraduate_part_time CHECK (((NOT ((degree)::text = 'PG'::text)) OR ((mode)::text = 'N'::text)))
);


--
-- Name: admissions_offer_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_offer ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_offer_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_profiledocument; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_profiledocument (
    id bigint NOT NULL,
    kind character varying(16) NOT NULL,
    version integer NOT NULL,
    file character varying(100) NOT NULL,
    original_name character varying(200) NOT NULL,
    sha256 character varying(64) NOT NULL,
    uploaded_at timestamp with time zone NOT NULL,
    user_id bigint NOT NULL,
    CONSTRAINT admissions_profiledocument_version_check CHECK ((version >= 0))
);


--
-- Name: admissions_profiledocument_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_profiledocument ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_profiledocument_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_profilephoto; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_profilephoto (
    id bigint NOT NULL,
    version integer NOT NULL,
    file character varying(100) NOT NULL,
    original_name character varying(200) NOT NULL,
    sha256 character varying(64) NOT NULL,
    uploaded_at timestamp with time zone NOT NULL,
    approved_at timestamp with time zone,
    approved_by_id bigint,
    user_id bigint NOT NULL,
    CONSTRAINT admissions_profilephoto_version_check CHECK ((version >= 0))
);


--
-- Name: admissions_profilephoto_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_profilephoto ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_profilephoto_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_program; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_program (
    id bigint NOT NULL,
    name character varying(200) NOT NULL,
    description text NOT NULL,
    source character varying(500) NOT NULL,
    illustrative boolean NOT NULL,
    faculty_id bigint NOT NULL
);


--
-- Name: admissions_program_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_program ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_program_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_program_partner_faculties; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_program_partner_faculties (
    id bigint NOT NULL,
    program_id bigint NOT NULL,
    faculty_id bigint NOT NULL
);


--
-- Name: admissions_program_partner_faculties_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_program_partner_faculties ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_program_partner_faculties_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_publication; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_publication (
    id bigint NOT NULL,
    version integer NOT NULL,
    published_at timestamp with time zone NOT NULL,
    reason text NOT NULL,
    cutoff numeric(8,2),
    qualified_count integer NOT NULL,
    available_places integer NOT NULL,
    overflow integer NOT NULL,
    rule jsonb NOT NULL,
    author_id bigint NOT NULL,
    offer_id bigint NOT NULL,
    round_id bigint NOT NULL,
    CONSTRAINT admissions_publication_available_places_check CHECK ((available_places >= 0)),
    CONSTRAINT admissions_publication_overflow_check CHECK ((overflow >= 0)),
    CONSTRAINT admissions_publication_qualified_count_check CHECK ((qualified_count >= 0)),
    CONSTRAINT admissions_publication_version_check CHECK ((version >= 0))
);


--
-- Name: admissions_publication_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_publication ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_publication_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_rankingentry; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_rankingentry (
    id bigint NOT NULL,
    rank integer NOT NULL,
    score numeric(8,2),
    decision character varying(12) NOT NULL,
    explanation jsonb NOT NULL,
    application_id bigint NOT NULL,
    publication_id bigint NOT NULL,
    CONSTRAINT admissions_rankingentry_rank_check CHECK ((rank >= 0))
);


--
-- Name: admissions_rankingentry_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_rankingentry ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_rankingentry_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_residence; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_residence (
    user_id bigint NOT NULL,
    city character varying(100) NOT NULL,
    street character varying(150) NOT NULL,
    building character varying(20) NOT NULL,
    apartment character varying(20) NOT NULL,
    postal_code character varying(6) NOT NULL,
    latitude numeric(9,6),
    longitude numeric(9,6),
    CONSTRAINT residence_coordinate_pair CHECK ((((latitude IS NULL) AND (longitude IS NULL)) OR ((latitude >= ('-90'::integer)::numeric) AND (latitude IS NOT NULL) AND (latitude <= (90)::numeric) AND (longitude >= ('-180'::integer)::numeric) AND (longitude IS NOT NULL) AND (longitude <= (180)::numeric))))
);


--
-- Name: admissions_round; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_round (
    id bigint NOT NULL,
    degree character varying(2) NOT NULL,
    number smallint NOT NULL,
    start timestamp with time zone NOT NULL,
    application_end timestamp with time zone NOT NULL,
    "end" timestamp with time zone NOT NULL,
    campaign_id bigint NOT NULL,
    CONSTRAINT admissions_round_number_check CHECK ((number >= 0)),
    CONSTRAINT round_dates CHECK (((start < application_end) AND (application_end < "end")))
);


--
-- Name: admissions_round_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_round ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_round_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_session; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_session (
    id bigint NOT NULL,
    key_hash character varying(64) NOT NULL,
    expires_at timestamp with time zone NOT NULL,
    user_id bigint NOT NULL
);


--
-- Name: admissions_session_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_session ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_session_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_user; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_user (
    id bigint NOT NULL,
    password character varying(128) NOT NULL,
    last_login timestamp with time zone,
    is_superuser boolean NOT NULL,
    username character varying(150) NOT NULL,
    first_name character varying(150) NOT NULL,
    last_name character varying(150) NOT NULL,
    is_staff boolean NOT NULL,
    is_active boolean NOT NULL,
    date_joined timestamp with time zone NOT NULL,
    email character varying(254) NOT NULL,
    role character varying(12) NOT NULL,
    recovery_hash character varying(128) NOT NULL,
    totp_secret character varying(64) NOT NULL,
    totp_pending character varying(64) NOT NULL,
    totp_last_step bigint NOT NULL,
    is_demo boolean NOT NULL
);


--
-- Name: admissions_user_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_user_groups (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    group_id integer NOT NULL
);


--
-- Name: admissions_user_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_user_groups ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_user_groups_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_user_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_user ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_user_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_user_user_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.admissions_user_user_permissions (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: admissions_user_user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.admissions_user_user_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.admissions_user_user_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group (
    id integer NOT NULL,
    name character varying(150) NOT NULL
);


--
-- Name: auth_group_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_group_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_group_permissions (
    id bigint NOT NULL,
    group_id integer NOT NULL,
    permission_id integer NOT NULL
);


--
-- Name: auth_group_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_group_permissions ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_group_permissions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: auth_permission; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auth_permission (
    id integer NOT NULL,
    name character varying(255) NOT NULL,
    content_type_id integer NOT NULL,
    codename character varying(100) NOT NULL
);


--
-- Name: auth_permission_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.auth_permission ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.auth_permission_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_content_type; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_content_type (
    id integer NOT NULL,
    app_label character varying(100) NOT NULL,
    model character varying(100) NOT NULL
);


--
-- Name: django_content_type_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_content_type ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_content_type_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: django_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.django_migrations (
    id bigint NOT NULL,
    app character varying(255) NOT NULL,
    name character varying(255) NOT NULL,
    applied timestamp with time zone NOT NULL
);


--
-- Name: django_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.django_migrations ALTER COLUMN id ADD GENERATED BY DEFAULT AS IDENTITY (
    SEQUENCE NAME public.django_migrations_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: pk_candidates_without_confirmed_place; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.pk_candidates_without_confirmed_place AS
 SELECT admissions_application.candidate_id
   FROM public.admissions_application
  WHERE ((admissions_application.status)::text = ANY ((ARRAY['verified'::character varying, 'qualified'::character varying, 'waitlist'::character varying])::text[]))
EXCEPT
 SELECT admissions_application.candidate_id
   FROM public.admissions_application
  WHERE ((admissions_application.status)::text = 'confirmed'::text);


--
-- Name: pk_offer_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pk_offer_stats (
    offer_id bigint NOT NULL,
    applications bigint DEFAULT 0 NOT NULL,
    verified bigint DEFAULT 0 NOT NULL,
    confirmed bigint DEFAULT 0 NOT NULL
);


--
-- Name: pk_offer_overview; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.pk_offer_overview AS
 SELECT o.id,
    p.name,
    f.code AS faculty,
    o.degree,
    o.mode,
    o.capacity,
    o.minimum,
    COALESCE(s.applications, (0)::bigint) AS applications,
    COALESCE(s.verified, (0)::bigint) AS verified,
    COALESCE(s.confirmed, (0)::bigint) AS confirmed
   FROM (((public.admissions_offer o
     JOIN public.admissions_program p ON ((p.id = o.program_id)))
     JOIN public.admissions_faculty f ON ((f.id = p.faculty_id)))
     LEFT JOIN public.pk_offer_stats s ON ((s.offer_id = o.id)));


--
-- Name: pk_row_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pk_row_audit (
    id bigint NOT NULL,
    occurred_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    transaction_id bigint DEFAULT txid_current() NOT NULL,
    db_actor text DEFAULT SESSION_USER NOT NULL,
    operation text NOT NULL,
    application_id bigint NOT NULL,
    before_state jsonb,
    after_state jsonb
);


--
-- Name: pk_row_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.pk_row_audit ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.pk_row_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: pk_statement_audit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.pk_statement_audit (
    id bigint NOT NULL,
    occurred_at timestamp with time zone DEFAULT clock_timestamp() NOT NULL,
    operation text NOT NULL,
    affected_rows bigint NOT NULL
);


--
-- Name: pk_statement_audit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

ALTER TABLE public.pk_statement_audit ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME public.pk_statement_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);


--
-- Name: admissions_academicaverage admissions_academicaverage_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_academicaverage
    ADD CONSTRAINT admissions_academicaverage_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_allowedprofession admissions_allowedprofession_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_allowedprofession
    ADD CONSTRAINT admissions_allowedprofession_pkey PRIMARY KEY (id);


--
-- Name: admissions_allowedsubject admissions_allowedsubject_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_allowedsubject
    ADD CONSTRAINT admissions_allowedsubject_pkey PRIMARY KEY (id);


--
-- Name: admissions_application admissions_application_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_application_pkey PRIMARY KEY (id);


--
-- Name: admissions_application admissions_application_public_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_application_public_id_key UNIQUE (public_id);


--
-- Name: admissions_application admissions_application_student_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_application_student_number_key UNIQUE (student_number);


--
-- Name: admissions_auditevent admissions_auditevent_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_auditevent
    ADD CONSTRAINT admissions_auditevent_pkey PRIMARY KEY (id);


--
-- Name: admissions_campaign admissions_campaign_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_campaign
    ADD CONSTRAINT admissions_campaign_pkey PRIMARY KEY (id);


--
-- Name: admissions_candidateidentity admissions_candidateidentity_pesel_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidateidentity
    ADD CONSTRAINT admissions_candidateidentity_pesel_key UNIQUE (pesel);


--
-- Name: admissions_candidateidentity admissions_candidateidentity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidateidentity
    ADD CONSTRAINT admissions_candidateidentity_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_candidatenotificationaddress admissions_candidatenotificationaddress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidatenotificationaddress
    ADD CONSTRAINT admissions_candidatenotificationaddress_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_candidatephone admissions_candidatephone_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidatephone
    ADD CONSTRAINT admissions_candidatephone_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_candidateportfolio admissions_candidateportfolio_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidateportfolio
    ADD CONSTRAINT admissions_candidateportfolio_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_contactanchor admissions_contactanchor_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_contactanchor
    ADD CONSTRAINT admissions_contactanchor_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_diploma admissions_diploma_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_diploma
    ADD CONSTRAINT admissions_diploma_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_document admissions_document_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_document
    ADD CONSTRAINT admissions_document_pkey PRIMARY KEY (id);


--
-- Name: admissions_dormitory admissions_dormitory_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_dormitory
    ADD CONSTRAINT admissions_dormitory_pkey PRIMARY KEY (code);


--
-- Name: admissions_emaildelivery admissions_emaildelivery_notification_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_emaildelivery
    ADD CONSTRAINT admissions_emaildelivery_notification_id_key UNIQUE (notification_id);


--
-- Name: admissions_emaildelivery admissions_emaildelivery_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_emaildelivery
    ADD CONSTRAINT admissions_emaildelivery_pkey PRIMARY KEY (id);


--
-- Name: admissions_examresult admissions_examresult_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_examresult
    ADD CONSTRAINT admissions_examresult_pkey PRIMARY KEY (id);


--
-- Name: admissions_faculty admissions_faculty_code_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_faculty
    ADD CONSTRAINT admissions_faculty_code_key UNIQUE (code);


--
-- Name: admissions_faculty admissions_faculty_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_faculty
    ADD CONSTRAINT admissions_faculty_pkey PRIMARY KEY (id);


--
-- Name: admissions_housingapplication admissions_housingapplication_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_housingapplication
    ADD CONSTRAINT admissions_housingapplication_pkey PRIMARY KEY (id);


--
-- Name: admissions_notification admissions_notification_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_notification
    ADD CONSTRAINT admissions_notification_pkey PRIMARY KEY (id);


--
-- Name: admissions_offer admissions_offer_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_offer
    ADD CONSTRAINT admissions_offer_pkey PRIMARY KEY (id);


--
-- Name: admissions_profiledocument admissions_profiledocument_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_profiledocument
    ADD CONSTRAINT admissions_profiledocument_pkey PRIMARY KEY (id);


--
-- Name: admissions_profilephoto admissions_profilephoto_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_profilephoto
    ADD CONSTRAINT admissions_profilephoto_pkey PRIMARY KEY (id);


--
-- Name: admissions_program_partner_faculties admissions_program_partn_program_id_faculty_id_529686d0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_program_partner_faculties
    ADD CONSTRAINT admissions_program_partn_program_id_faculty_id_529686d0_uniq UNIQUE (program_id, faculty_id);


--
-- Name: admissions_program_partner_faculties admissions_program_partner_faculties_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_program_partner_faculties
    ADD CONSTRAINT admissions_program_partner_faculties_pkey PRIMARY KEY (id);


--
-- Name: admissions_program admissions_program_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_program
    ADD CONSTRAINT admissions_program_pkey PRIMARY KEY (id);


--
-- Name: admissions_publication admissions_publication_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_publication
    ADD CONSTRAINT admissions_publication_pkey PRIMARY KEY (id);


--
-- Name: admissions_rankingentry admissions_rankingentry_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_rankingentry
    ADD CONSTRAINT admissions_rankingentry_pkey PRIMARY KEY (id);


--
-- Name: admissions_residence admissions_residence_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_residence
    ADD CONSTRAINT admissions_residence_pkey PRIMARY KEY (user_id);


--
-- Name: admissions_round admissions_round_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_round
    ADD CONSTRAINT admissions_round_pkey PRIMARY KEY (id);


--
-- Name: admissions_session admissions_session_key_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_session
    ADD CONSTRAINT admissions_session_key_hash_key UNIQUE (key_hash);


--
-- Name: admissions_session admissions_session_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_session
    ADD CONSTRAINT admissions_session_pkey PRIMARY KEY (id);


--
-- Name: admissions_user admissions_user_email_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user
    ADD CONSTRAINT admissions_user_email_key UNIQUE (email);


--
-- Name: admissions_user_groups admissions_user_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_groups
    ADD CONSTRAINT admissions_user_groups_pkey PRIMARY KEY (id);


--
-- Name: admissions_user_groups admissions_user_groups_user_id_group_id_23dc7cd2_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_groups
    ADD CONSTRAINT admissions_user_groups_user_id_group_id_23dc7cd2_uniq UNIQUE (user_id, group_id);


--
-- Name: admissions_user admissions_user_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user
    ADD CONSTRAINT admissions_user_pkey PRIMARY KEY (id);


--
-- Name: admissions_user_user_permissions admissions_user_user_per_user_id_permission_id_7fbb6cb6_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_user_permissions
    ADD CONSTRAINT admissions_user_user_per_user_id_permission_id_7fbb6cb6_uniq UNIQUE (user_id, permission_id);


--
-- Name: admissions_user_user_permissions admissions_user_user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_user_permissions
    ADD CONSTRAINT admissions_user_user_permissions_pkey PRIMARY KEY (id);


--
-- Name: admissions_user admissions_user_username_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user
    ADD CONSTRAINT admissions_user_username_key UNIQUE (username);


--
-- Name: admissions_allowedsubject allowed_subject_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_allowedsubject
    ADD CONSTRAINT allowed_subject_unique UNIQUE (offer_id, subject);


--
-- Name: auth_group auth_group_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_name_key UNIQUE (name);


--
-- Name: auth_group_permissions auth_group_permissions_group_id_permission_id_0cd325b0_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_permission_id_0cd325b0_uniq UNIQUE (group_id, permission_id);


--
-- Name: auth_group_permissions auth_group_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_pkey PRIMARY KEY (id);


--
-- Name: auth_group auth_group_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group
    ADD CONSTRAINT auth_group_pkey PRIMARY KEY (id);


--
-- Name: auth_permission auth_permission_content_type_id_codename_01ab375a_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_codename_01ab375a_uniq UNIQUE (content_type_id, codename);


--
-- Name: auth_permission auth_permission_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_pkey PRIMARY KEY (id);


--
-- Name: django_content_type django_content_type_app_label_model_76bd3d3b_uniq; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_app_label_model_76bd3d3b_uniq UNIQUE (app_label, model);


--
-- Name: django_content_type django_content_type_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_content_type
    ADD CONSTRAINT django_content_type_pkey PRIMARY KEY (id);


--
-- Name: django_migrations django_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.django_migrations
    ADD CONSTRAINT django_migrations_pkey PRIMARY KEY (id);


--
-- Name: admissions_document document_revision; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_document
    ADD CONSTRAINT document_revision UNIQUE (application_id, kind, revision);


--
-- Name: admissions_application one_application_per_offer; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT one_application_per_offer UNIQUE (candidate_id, offer_id);


--
-- Name: admissions_examresult one_exam_result; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_examresult
    ADD CONSTRAINT one_exam_result UNIQUE (user_id, subject, level);


--
-- Name: admissions_housingapplication one_housing_request; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_housingapplication
    ADD CONSTRAINT one_housing_request UNIQUE (candidate_id, campaign_id);


--
-- Name: admissions_rankingentry one_ranking_entry; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_rankingentry
    ADD CONSTRAINT one_ranking_entry UNIQUE (publication_id, application_id);


--
-- Name: admissions_round one_round; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_round
    ADD CONSTRAINT one_round UNIQUE (campaign_id, degree, number);


--
-- Name: pk_offer_stats pk_offer_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pk_offer_stats
    ADD CONSTRAINT pk_offer_stats_pkey PRIMARY KEY (offer_id);


--
-- Name: pk_row_audit pk_row_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pk_row_audit
    ADD CONSTRAINT pk_row_audit_pkey PRIMARY KEY (id);


--
-- Name: pk_statement_audit pk_statement_audit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pk_statement_audit
    ADD CONSTRAINT pk_statement_audit_pkey PRIMARY KEY (id);


--
-- Name: admissions_allowedprofession profession_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_allowedprofession
    ADD CONSTRAINT profession_unique UNIQUE (offer_id, name);


--
-- Name: admissions_profiledocument profile_document_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_profiledocument
    ADD CONSTRAINT profile_document_version UNIQUE (user_id, kind, version);


--
-- Name: admissions_profilephoto profile_photo_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_profilephoto
    ADD CONSTRAINT profile_photo_version UNIQUE (user_id, version);


--
-- Name: admissions_program program_faculty_name; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_program
    ADD CONSTRAINT program_faculty_name UNIQUE (name, faculty_id);


--
-- Name: admissions_publication publication_version; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_publication
    ADD CONSTRAINT publication_version UNIQUE (offer_id, round_id, version);


--
-- Name: admissions_offer unique_offer; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_offer
    ADD CONSTRAINT unique_offer UNIQUE (campaign_id, program_id, degree, mode);


--
-- Name: admissions_allowedprofession_offer_id_85dcde20; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_allowedprofession_offer_id_85dcde20 ON public.admissions_allowedprofession USING btree (offer_id);


--
-- Name: admissions_allowedsubject_offer_id_e56b7f5c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_allowedsubject_offer_id_e56b7f5c ON public.admissions_allowedsubject USING btree (offer_id);


--
-- Name: admissions_application_candidate_id_bc69d823; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_application_candidate_id_bc69d823 ON public.admissions_application USING btree (candidate_id);


--
-- Name: admissions_application_oath_photo_id_84d9f886; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_application_oath_photo_id_84d9f886 ON public.admissions_application USING btree (oath_photo_id);


--
-- Name: admissions_application_offer_id_f69e8b11; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_application_offer_id_f69e8b11 ON public.admissions_application USING btree (offer_id);


--
-- Name: admissions_application_reviewed_by_id_f275eef6; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_application_reviewed_by_id_f275eef6 ON public.admissions_application USING btree (reviewed_by_id);


--
-- Name: admissions_application_round_id_edd3fa67; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_application_round_id_edd3fa67 ON public.admissions_application USING btree (round_id);


--
-- Name: admissions_application_student_number_81335493_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_application_student_number_81335493_like ON public.admissions_application USING btree (student_number varchar_pattern_ops);


--
-- Name: admissions_auditevent_actor_id_659c16ef; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_auditevent_actor_id_659c16ef ON public.admissions_auditevent USING btree (actor_id);


--
-- Name: admissions_candidateidentity_pesel_4d8d8336_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_candidateidentity_pesel_4d8d8336_like ON public.admissions_candidateidentity USING btree (pesel varchar_pattern_ops);


--
-- Name: admissions_document_application_id_20bf69fa; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_document_application_id_20bf69fa ON public.admissions_document USING btree (application_id);


--
-- Name: admissions_document_profile_source_id_23990467; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_document_profile_source_id_23990467 ON public.admissions_document USING btree (profile_source_id);


--
-- Name: admissions_document_reused_from_id_28380dca; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_document_reused_from_id_28380dca ON public.admissions_document USING btree (reused_from_id);


--
-- Name: admissions_dormitory_code_714b7aca_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_dormitory_code_714b7aca_like ON public.admissions_dormitory USING btree (code varchar_pattern_ops);


--
-- Name: admissions_examresult_user_id_f7de4132; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_examresult_user_id_f7de4132 ON public.admissions_examresult USING btree (user_id);


--
-- Name: admissions_faculty_code_98facbdc_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_faculty_code_98facbdc_like ON public.admissions_faculty USING btree (code varchar_pattern_ops);


--
-- Name: admissions_housingapplication_allocated_id_f67c70e5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_housingapplication_allocated_id_f67c70e5 ON public.admissions_housingapplication USING btree (allocated_id);


--
-- Name: admissions_housingapplication_allocated_id_f67c70e5_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_housingapplication_allocated_id_f67c70e5_like ON public.admissions_housingapplication USING btree (allocated_id varchar_pattern_ops);


--
-- Name: admissions_housingapplication_campaign_id_13dfa3ad; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_housingapplication_campaign_id_13dfa3ad ON public.admissions_housingapplication USING btree (campaign_id);


--
-- Name: admissions_housingapplication_candidate_id_4a347183; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_housingapplication_candidate_id_4a347183 ON public.admissions_housingapplication USING btree (candidate_id);


--
-- Name: admissions_housingapplication_enrollment_id_30b5cb1f; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_housingapplication_enrollment_id_30b5cb1f ON public.admissions_housingapplication USING btree (enrollment_id);


--
-- Name: admissions_housingapplication_preferred_id_14f8b4c1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_housingapplication_preferred_id_14f8b4c1 ON public.admissions_housingapplication USING btree (preferred_id);


--
-- Name: admissions_housingapplication_preferred_id_14f8b4c1_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_housingapplication_preferred_id_14f8b4c1_like ON public.admissions_housingapplication USING btree (preferred_id varchar_pattern_ops);


--
-- Name: admissions_notification_user_id_c4d349f7; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_notification_user_id_c4d349f7 ON public.admissions_notification USING btree (user_id);


--
-- Name: admissions_offer_campaign_id_f3964ec1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_offer_campaign_id_f3964ec1 ON public.admissions_offer USING btree (campaign_id);


--
-- Name: admissions_offer_program_id_8c346efc; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_offer_program_id_8c346efc ON public.admissions_offer USING btree (program_id);


--
-- Name: admissions_profiledocument_user_id_0946c593; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_profiledocument_user_id_0946c593 ON public.admissions_profiledocument USING btree (user_id);


--
-- Name: admissions_profilephoto_approved_by_id_afac4a63; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_profilephoto_approved_by_id_afac4a63 ON public.admissions_profilephoto USING btree (approved_by_id);


--
-- Name: admissions_profilephoto_user_id_ec5f0a4b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_profilephoto_user_id_ec5f0a4b ON public.admissions_profilephoto USING btree (user_id);


--
-- Name: admissions_program_faculty_id_7c5bd2e9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_program_faculty_id_7c5bd2e9 ON public.admissions_program USING btree (faculty_id);


--
-- Name: admissions_program_partner_faculties_faculty_id_d5ff5431; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_program_partner_faculties_faculty_id_d5ff5431 ON public.admissions_program_partner_faculties USING btree (faculty_id);


--
-- Name: admissions_program_partner_faculties_program_id_d6a69868; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_program_partner_faculties_program_id_d6a69868 ON public.admissions_program_partner_faculties USING btree (program_id);


--
-- Name: admissions_publication_author_id_a18dc5e2; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_publication_author_id_a18dc5e2 ON public.admissions_publication USING btree (author_id);


--
-- Name: admissions_publication_offer_id_084e2987; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_publication_offer_id_084e2987 ON public.admissions_publication USING btree (offer_id);


--
-- Name: admissions_publication_round_id_8787344e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_publication_round_id_8787344e ON public.admissions_publication USING btree (round_id);


--
-- Name: admissions_rankingentry_application_id_dedff4ea; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_rankingentry_application_id_dedff4ea ON public.admissions_rankingentry USING btree (application_id);


--
-- Name: admissions_rankingentry_publication_id_d68f1f5c; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_rankingentry_publication_id_d68f1f5c ON public.admissions_rankingentry USING btree (publication_id);


--
-- Name: admissions_round_campaign_id_e3f38220; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_round_campaign_id_e3f38220 ON public.admissions_round USING btree (campaign_id);


--
-- Name: admissions_session_key_hash_3861c63c_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_session_key_hash_3861c63c_like ON public.admissions_session USING btree (key_hash varchar_pattern_ops);


--
-- Name: admissions_session_user_id_523e9cc3; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_session_user_id_523e9cc3 ON public.admissions_session USING btree (user_id);


--
-- Name: admissions_user_email_b536f6de_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_user_email_b536f6de_like ON public.admissions_user USING btree (email varchar_pattern_ops);


--
-- Name: admissions_user_groups_group_id_6b06e31d; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_user_groups_group_id_6b06e31d ON public.admissions_user_groups USING btree (group_id);


--
-- Name: admissions_user_groups_user_id_aed6aad0; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_user_groups_user_id_aed6aad0 ON public.admissions_user_groups USING btree (user_id);


--
-- Name: admissions_user_user_permissions_permission_id_a9dcc3a5; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_user_user_permissions_permission_id_a9dcc3a5 ON public.admissions_user_user_permissions USING btree (permission_id);


--
-- Name: admissions_user_user_permissions_user_id_72e2bd75; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_user_user_permissions_user_id_72e2bd75 ON public.admissions_user_user_permissions USING btree (user_id);


--
-- Name: admissions_user_username_af941b82_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX admissions_user_username_af941b82_like ON public.admissions_user USING btree (username varchar_pattern_ops);


--
-- Name: application_queue; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX application_queue ON public.admissions_application USING btree (offer_id, status, submitted_at);


--
-- Name: application_snapshot_gin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX application_snapshot_gin ON public.admissions_application USING gin (input_snapshot jsonb_path_ops);


--
-- Name: application_verified_partial; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX application_verified_partial ON public.admissions_application USING btree (offer_id, round_id, submitted_at, id) WHERE ((status)::text = ANY ((ARRAY['verified'::character varying, 'qualified'::character varying, 'waitlist'::character varying, 'confirmed'::character varying])::text[]));


--
-- Name: audit_recent; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_recent ON public.admissions_auditevent USING btree (created_at DESC);


--
-- Name: audit_time_brin; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX audit_time_brin ON public.pk_row_audit USING brin (occurred_at);


--
-- Name: auth_group_name_a6ea08ec_like; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_name_a6ea08ec_like ON public.auth_group USING btree (name varchar_pattern_ops);


--
-- Name: auth_group_permissions_group_id_b120cbf9; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_group_id_b120cbf9 ON public.auth_group_permissions USING btree (group_id);


--
-- Name: auth_group_permissions_permission_id_84c5c92e; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_group_permissions_permission_id_84c5c92e ON public.auth_group_permissions USING btree (permission_id);


--
-- Name: auth_permission_content_type_id_2f476e4b; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX auth_permission_content_type_id_2f476e4b ON public.auth_permission USING btree (content_type_id);


--
-- Name: candidate_applications; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX candidate_applications ON public.admissions_application USING btree (candidate_id, created_at DESC);


--
-- Name: email_delivery_ready_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX email_delivery_ready_idx ON public.admissions_emaildelivery USING btree (state, available_at);


--
-- Name: housing_campaign_distance; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX housing_campaign_distance ON public.admissions_housingapplication USING btree (campaign_id, status, distance_km DESC);


--
-- Name: program_lower_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX program_lower_name ON public.admissions_program USING btree (lower((name)::text));


--
-- Name: ranking_order; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ranking_order ON public.admissions_rankingentry USING btree (publication_id, rank);


--
-- Name: admissions_application application_delete_statement; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER application_delete_statement AFTER DELETE ON public.admissions_application REFERENCING OLD TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION public.pk_application_statement_audit();


--
-- Name: admissions_application application_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER application_guard BEFORE INSERT OR UPDATE ON public.admissions_application FOR EACH ROW EXECUTE FUNCTION public.pk_application_guard();


--
-- Name: admissions_application application_insert_statement; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER application_insert_statement AFTER INSERT ON public.admissions_application REFERENCING NEW TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION public.pk_application_statement_audit();


--
-- Name: admissions_application application_row_audit; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER application_row_audit AFTER INSERT OR DELETE OR UPDATE ON public.admissions_application FOR EACH ROW EXECUTE FUNCTION public.pk_application_audit();


--
-- Name: admissions_application application_update_statement; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER application_update_statement AFTER UPDATE ON public.admissions_application REFERENCING NEW TABLE AS changed FOR EACH STATEMENT EXECUTE FUNCTION public.pk_application_statement_audit();


--
-- Name: admissions_candidatecontact contact_write; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER contact_write INSTEAD OF INSERT OR DELETE OR UPDATE ON public.admissions_candidatecontact FOR EACH ROW EXECUTE FUNCTION public.pk_contact_write();


--
-- Name: admissions_publication immutable_publication; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER immutable_publication BEFORE DELETE OR UPDATE ON public.admissions_publication FOR EACH ROW EXECUTE FUNCTION public.pk_immutable_publication();


--
-- Name: admissions_rankingentry immutable_ranking_entry; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER immutable_ranking_entry BEFORE DELETE OR UPDATE ON public.admissions_rankingentry FOR EACH ROW EXECUTE FUNCTION public.pk_immutable_publication();


--
-- Name: admissions_application oath_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER oath_guard BEFORE INSERT OR UPDATE ON public.admissions_application FOR EACH ROW EXECUTE FUNCTION public.pk_oath_guard();


--
-- Name: admissions_document photo_freeze; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER photo_freeze BEFORE INSERT OR UPDATE ON public.admissions_document FOR EACH ROW EXECUTE FUNCTION public.pk_photo_freeze();


--
-- Name: admissions_profilephoto profile_photo_guard; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER profile_photo_guard BEFORE UPDATE ON public.admissions_profilephoto FOR EACH ROW EXECUTE FUNCTION public.pk_profile_photo_guard();


--
-- Name: admissions_academicaverage admissions_academica_user_id_1a100cb2_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_academicaverage
    ADD CONSTRAINT admissions_academica_user_id_1a100cb2_fk_admission FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_allowedprofession admissions_allowedpr_offer_id_85dcde20_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_allowedprofession
    ADD CONSTRAINT admissions_allowedpr_offer_id_85dcde20_fk_admission FOREIGN KEY (offer_id) REFERENCES public.admissions_offer(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_allowedsubject admissions_allowedsu_offer_id_e56b7f5c_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_allowedsubject
    ADD CONSTRAINT admissions_allowedsu_offer_id_e56b7f5c_fk_admission FOREIGN KEY (offer_id) REFERENCES public.admissions_offer(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_application admissions_applicati_candidate_id_bc69d823_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_applicati_candidate_id_bc69d823_fk_admission FOREIGN KEY (candidate_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_application admissions_applicati_oath_photo_id_84d9f886_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_applicati_oath_photo_id_84d9f886_fk_admission FOREIGN KEY (oath_photo_id) REFERENCES public.admissions_profilephoto(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_application admissions_applicati_reviewed_by_id_f275eef6_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_applicati_reviewed_by_id_f275eef6_fk_admission FOREIGN KEY (reviewed_by_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_application admissions_application_offer_id_f69e8b11_fk_admissions_offer_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_application_offer_id_f69e8b11_fk_admissions_offer_id FOREIGN KEY (offer_id) REFERENCES public.admissions_offer(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_application admissions_application_round_id_edd3fa67_fk_admissions_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_application
    ADD CONSTRAINT admissions_application_round_id_edd3fa67_fk_admissions_round_id FOREIGN KEY (round_id) REFERENCES public.admissions_round(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_auditevent admissions_auditevent_actor_id_659c16ef_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_auditevent
    ADD CONSTRAINT admissions_auditevent_actor_id_659c16ef_fk_admissions_user_id FOREIGN KEY (actor_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_candidatenotificationaddress admissions_candidate_user_id_1680d9c0_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidatenotificationaddress
    ADD CONSTRAINT admissions_candidate_user_id_1680d9c0_fk_admission FOREIGN KEY (user_id) REFERENCES public.admissions_contactanchor(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_candidateportfolio admissions_candidate_user_id_3ae462f8_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidateportfolio
    ADD CONSTRAINT admissions_candidate_user_id_3ae462f8_fk_admission FOREIGN KEY (user_id) REFERENCES public.admissions_contactanchor(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_candidateidentity admissions_candidate_user_id_775e4a35_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidateidentity
    ADD CONSTRAINT admissions_candidate_user_id_775e4a35_fk_admission FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_candidatephone admissions_candidate_user_id_ada009aa_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_candidatephone
    ADD CONSTRAINT admissions_candidate_user_id_ada009aa_fk_admission FOREIGN KEY (user_id) REFERENCES public.admissions_contactanchor(user_id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_contactanchor admissions_contactanchor_user_id_2e578bb6_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_contactanchor
    ADD CONSTRAINT admissions_contactanchor_user_id_2e578bb6_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_diploma admissions_diploma_user_id_77375c8a_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_diploma
    ADD CONSTRAINT admissions_diploma_user_id_77375c8a_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_document admissions_document_application_id_20bf69fa_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_document
    ADD CONSTRAINT admissions_document_application_id_20bf69fa_fk_admission FOREIGN KEY (application_id) REFERENCES public.admissions_application(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_document admissions_document_profile_source_id_23990467_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_document
    ADD CONSTRAINT admissions_document_profile_source_id_23990467_fk_admission FOREIGN KEY (profile_source_id) REFERENCES public.admissions_profiledocument(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_document admissions_document_reused_from_id_28380dca_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_document
    ADD CONSTRAINT admissions_document_reused_from_id_28380dca_fk_admission FOREIGN KEY (reused_from_id) REFERENCES public.admissions_document(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_emaildelivery admissions_emaildeli_notification_id_bf73f48e_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_emaildelivery
    ADD CONSTRAINT admissions_emaildeli_notification_id_bf73f48e_fk_admission FOREIGN KEY (notification_id) REFERENCES public.admissions_notification(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_examresult admissions_examresult_user_id_f7de4132_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_examresult
    ADD CONSTRAINT admissions_examresult_user_id_f7de4132_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_housingapplication admissions_housingap_allocated_id_f67c70e5_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_housingapplication
    ADD CONSTRAINT admissions_housingap_allocated_id_f67c70e5_fk_admission FOREIGN KEY (allocated_id) REFERENCES public.admissions_dormitory(code) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_housingapplication admissions_housingap_campaign_id_13dfa3ad_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_housingapplication
    ADD CONSTRAINT admissions_housingap_campaign_id_13dfa3ad_fk_admission FOREIGN KEY (campaign_id) REFERENCES public.admissions_campaign(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_housingapplication admissions_housingap_candidate_id_4a347183_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_housingapplication
    ADD CONSTRAINT admissions_housingap_candidate_id_4a347183_fk_admission FOREIGN KEY (candidate_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_housingapplication admissions_housingap_enrollment_id_30b5cb1f_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_housingapplication
    ADD CONSTRAINT admissions_housingap_enrollment_id_30b5cb1f_fk_admission FOREIGN KEY (enrollment_id) REFERENCES public.admissions_application(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_housingapplication admissions_housingap_preferred_id_14f8b4c1_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_housingapplication
    ADD CONSTRAINT admissions_housingap_preferred_id_14f8b4c1_fk_admission FOREIGN KEY (preferred_id) REFERENCES public.admissions_dormitory(code) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_notification admissions_notification_user_id_c4d349f7_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_notification
    ADD CONSTRAINT admissions_notification_user_id_c4d349f7_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_offer admissions_offer_campaign_id_f3964ec1_fk_admissions_campaign_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_offer
    ADD CONSTRAINT admissions_offer_campaign_id_f3964ec1_fk_admissions_campaign_id FOREIGN KEY (campaign_id) REFERENCES public.admissions_campaign(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_offer admissions_offer_program_id_8c346efc_fk_admissions_program_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_offer
    ADD CONSTRAINT admissions_offer_program_id_8c346efc_fk_admissions_program_id FOREIGN KEY (program_id) REFERENCES public.admissions_program(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_profiledocument admissions_profiledo_user_id_0946c593_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_profiledocument
    ADD CONSTRAINT admissions_profiledo_user_id_0946c593_fk_admission FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_profilephoto admissions_profileph_approved_by_id_afac4a63_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_profilephoto
    ADD CONSTRAINT admissions_profileph_approved_by_id_afac4a63_fk_admission FOREIGN KEY (approved_by_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_profilephoto admissions_profilephoto_user_id_ec5f0a4b_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_profilephoto
    ADD CONSTRAINT admissions_profilephoto_user_id_ec5f0a4b_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_program admissions_program_faculty_id_7c5bd2e9_fk_admissions_faculty_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_program
    ADD CONSTRAINT admissions_program_faculty_id_7c5bd2e9_fk_admissions_faculty_id FOREIGN KEY (faculty_id) REFERENCES public.admissions_faculty(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_program_partner_faculties admissions_program_p_faculty_id_d5ff5431_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_program_partner_faculties
    ADD CONSTRAINT admissions_program_p_faculty_id_d5ff5431_fk_admission FOREIGN KEY (faculty_id) REFERENCES public.admissions_faculty(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_program_partner_faculties admissions_program_p_program_id_d6a69868_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_program_partner_faculties
    ADD CONSTRAINT admissions_program_p_program_id_d6a69868_fk_admission FOREIGN KEY (program_id) REFERENCES public.admissions_program(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_publication admissions_publication_author_id_a18dc5e2_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_publication
    ADD CONSTRAINT admissions_publication_author_id_a18dc5e2_fk_admissions_user_id FOREIGN KEY (author_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_publication admissions_publication_offer_id_084e2987_fk_admissions_offer_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_publication
    ADD CONSTRAINT admissions_publication_offer_id_084e2987_fk_admissions_offer_id FOREIGN KEY (offer_id) REFERENCES public.admissions_offer(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_publication admissions_publication_round_id_8787344e_fk_admissions_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_publication
    ADD CONSTRAINT admissions_publication_round_id_8787344e_fk_admissions_round_id FOREIGN KEY (round_id) REFERENCES public.admissions_round(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_rankingentry admissions_rankingen_application_id_dedff4ea_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_rankingentry
    ADD CONSTRAINT admissions_rankingen_application_id_dedff4ea_fk_admission FOREIGN KEY (application_id) REFERENCES public.admissions_application(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_rankingentry admissions_rankingen_publication_id_d68f1f5c_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_rankingentry
    ADD CONSTRAINT admissions_rankingen_publication_id_d68f1f5c_fk_admission FOREIGN KEY (publication_id) REFERENCES public.admissions_publication(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_residence admissions_residence_user_id_e0b68702_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_residence
    ADD CONSTRAINT admissions_residence_user_id_e0b68702_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_round admissions_round_campaign_id_e3f38220_fk_admissions_campaign_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_round
    ADD CONSTRAINT admissions_round_campaign_id_e3f38220_fk_admissions_campaign_id FOREIGN KEY (campaign_id) REFERENCES public.admissions_campaign(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_session admissions_session_user_id_523e9cc3_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_session
    ADD CONSTRAINT admissions_session_user_id_523e9cc3_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_user_groups admissions_user_groups_group_id_6b06e31d_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_groups
    ADD CONSTRAINT admissions_user_groups_group_id_6b06e31d_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_user_groups admissions_user_groups_user_id_aed6aad0_fk_admissions_user_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_groups
    ADD CONSTRAINT admissions_user_groups_user_id_aed6aad0_fk_admissions_user_id FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_user_user_permissions admissions_user_user_permission_id_a9dcc3a5_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_user_permissions
    ADD CONSTRAINT admissions_user_user_permission_id_a9dcc3a5_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: admissions_user_user_permissions admissions_user_user_user_id_72e2bd75_fk_admission; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.admissions_user_user_permissions
    ADD CONSTRAINT admissions_user_user_user_id_72e2bd75_fk_admission FOREIGN KEY (user_id) REFERENCES public.admissions_user(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissio_permission_id_84c5c92e_fk_auth_perm; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissio_permission_id_84c5c92e_fk_auth_perm FOREIGN KEY (permission_id) REFERENCES public.auth_permission(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_group_permissions auth_group_permissions_group_id_b120cbf9_fk_auth_group_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_group_permissions
    ADD CONSTRAINT auth_group_permissions_group_id_b120cbf9_fk_auth_group_id FOREIGN KEY (group_id) REFERENCES public.auth_group(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: auth_permission auth_permission_content_type_id_2f476e4b_fk_django_co; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auth_permission
    ADD CONSTRAINT auth_permission_content_type_id_2f476e4b_fk_django_co FOREIGN KEY (content_type_id) REFERENCES public.django_content_type(id) DEFERRABLE INITIALLY DEFERRED;


--
-- Name: pk_offer_stats pk_offer_stats_offer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.pk_offer_stats
    ADD CONSTRAINT pk_offer_stats_offer_id_fkey FOREIGN KEY (offer_id) REFERENCES public.admissions_offer(id);


--
-- PostgreSQL database dump complete
--

\unrestrict roMXHST3aGuGAQ89bNA3xt39nFwP0X976aXVNy0IVslGw9gbkzKKQ8Vf8G6AyY9

