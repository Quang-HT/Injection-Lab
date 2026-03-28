import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";

import { getChallenge, runSimulation } from "../api";
import FooterNote from "../components/FooterNote";
import QueryPreviewBox from "../components/QueryPreviewBox";
import ResultConsole from "../components/ResultConsole";
import { useAppContext } from "../context/AppContext";
import {
  buildCategoryResult,
  buildSimulationQuery,
  getChallengeId,
  getFlagTitle,
  getInputLabel,
  getLabPageTitle,
  getResultTitle,
  getVisibleFields,
  shouldShowQueryPreview,
  shouldShowResultBox,
  shouldUseManualSubmit,
} from "../lib";

function buildInitialValues(fields) {
  return fields.reduce((accumulator, field) => {
    accumulator[field.name] = field.default_value ?? "";
    return accumulator;
  }, {});
}

export default function LabPage() {
  const { categorySlug, level } = useParams();
  const { userId, bootstrap, applyBootstrapSnapshot } = useAppContext();
  const [challenge, setChallenge] = useState(null);
  const [formValues, setFormValues] = useState({});
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const challengeId = getChallengeId(categorySlug, level);

  useEffect(() => {
    let ignore = false;

    async function loadChallenge() {
      setLoading(true);
      try {
        const payload = await getChallenge(userId, challengeId);
        if (!ignore) {
          setChallenge(payload);
          setFormValues(buildInitialValues(payload.fields));
          setResult(null);
          setError("");
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError.message);
        }
      } finally {
        if (!ignore) {
          setLoading(false);
        }
      }
    }

    loadChallenge();
    return () => {
      ignore = true;
    };
  }, [challengeId, userId]);

  const categoryMeta = bootstrap?.categories?.find((category) => category.slug === categorySlug);
  const visibleFields = useMemo(() => getVisibleFields(challenge), [challenge]);
  const usesManualSubmit = shouldUseManualSubmit(challenge);
  const showQueryPreview = shouldShowQueryPreview(challenge);
  const showResultBox = shouldShowResultBox(challenge);
  const renderedQuery = buildSimulationQuery(challenge, formValues);
  const resultText = error || buildCategoryResult(challenge, result, formValues);
  const flagText = !error && result?.flag ? result.flag : "";
  const inputLabel = getInputLabel(challenge, visibleFields, formValues);
  const pageTitle = getLabPageTitle(challenge);
  const timeNote = error
    ? error
    : result
      ? `Thời gian phản hồi: ${result.delay_ms} ms`
      : "Thời gian phản hồi sẽ thay đổi khi điều kiện khớp.";

  async function executeSimulation(nextInputs = formValues) {
    try {
      const payload = await runSimulation(userId, challengeId, nextInputs);
      setChallenge(payload.challenge);
      setResult(payload.result);
      applyBootstrapSnapshot(payload.bootstrap);
      setError("");
    } catch (requestError) {
      setError(requestError.message);
    }
  }

  useEffect(() => {
    if (!challenge || usesManualSubmit || visibleFields.length !== 1) {
      return undefined;
    }

    const field = visibleFields[0];
    const fieldValue = formValues[field.name] ?? "";
    if (!fieldValue.trim()) {
      setResult(null);
      return undefined;
    }

    const timer = window.setTimeout(() => {
      executeSimulation(formValues);
    }, 260);

    return () => window.clearTimeout(timer);
  }, [applyBootstrapSnapshot, challenge, formValues, usesManualSubmit, visibleFields]);

  async function handleSubmit(event) {
    event.preventDefault();
    await executeSimulation(formValues);
  }

  if (loading) {
    return <div className="sql-page sql-feedback">Đang tải...</div>;
  }

  if (error && !challenge) {
    return <div className="sql-page sql-feedback sql-feedback-error">{error}</div>;
  }

  return (
    <div className="sql-page">
      <section className="sql-page-head">
        <div className="sql-hero-icon" />
        <h1 className="sql-page-title">{pageTitle}</h1>
      </section>

      {categoryMeta?.levels?.length > 1 ? (
        <nav className="sql-level-nav" aria-label="Điều hướng level">
          {categoryMeta.levels.map((entry) => (
            <Link
              key={entry.level}
              to={`/lab/${categorySlug}/${entry.level}`}
              className={Number(level) === entry.level ? "sql-level-link active" : "sql-level-link"}
            >
              Level {entry.level}
            </Link>
          ))}
        </nav>
      ) : null}

      <section className="sql-workarea">
        {challenge?.filter_notice ? (
          <div className="sql-filter-note">
            <span className="sql-filter-note-label">Filter hiện tại:</span>
            <span>{challenge.filter_notice}</span>
          </div>
        ) : null}

        <div className="sql-label">{inputLabel}</div>

        <form onSubmit={handleSubmit}>
          <div className={visibleFields.length > 1 ? "sql-field-stack" : ""}>
            {visibleFields.map((field) => {
              const value = formValues[field.name] ?? "";
              const commonProps = {
                key: field.name,
                value,
                placeholder: "",
                spellCheck: false,
                onChange: (event) =>
                  setFormValues((current) => ({
                    ...current,
                    [field.name]: event.target.value,
                  })),
              };

              return (
                <label key={`${field.name}-label`} className="sql-field-wrap">
                  {visibleFields.length > 1 ? <span className="sql-field-label">{field.label}</span> : null}
                  {field.multiline ? (
                    <textarea {...commonProps} className="sql-input sql-multiline-input" />
                  ) : (
                    <input
                      {...commonProps}
                      className="sql-input single-line"
                      type={field.name === "password" ? "password" : "text"}
                    />
                  )}
                </label>
              );
            })}
          </div>

          {usesManualSubmit ? (
            <div className="sql-button-row">
              <button type="submit" className="sql-submit-button">
                Thực thi
              </button>
            </div>
          ) : null}
        </form>

        {showQueryPreview ? <div className="sql-divider" /> : null}

        {showQueryPreview ? <QueryPreviewBox title="Câu Query:" content={renderedQuery} /> : null}

        {showResultBox ? (
          <ResultConsole title={getResultTitle(challenge)} content={resultText} />
        ) : (
          <div className="sql-timer-note">{timeNote}</div>
        )}

        {flagText ? <ResultConsole title={getFlagTitle(challenge)} content={flagText} compact tone="flag" /> : null}
      </section>

      <FooterNote />
    </div>
  );
}
