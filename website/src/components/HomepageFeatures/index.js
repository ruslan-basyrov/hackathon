import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

const FeatureList = [
  {
    icon: '🔍',
    title: 'Decisions in code, not weights',
    description: (
      <>
        The state machine, the detection layer, and the per-persona policy are
        all readable code — the rubric&apos;s &quot;traceable decision rules.&quot;
        The model only produces behavior and words, never the when/how of an
        intervention.
      </>
    ),
  },
  {
    icon: '📊',
    title: 'Measurement substrate first',
    description: (
      <>
        The eval harness is the scaffold, not the finale. A seeded episode loop
        measures conversion with and without the coach on identical seeds — so
        the coach is the only variable, and every phase re-runs the same harness.
      </>
    ),
  },
  {
    icon: '🔌',
    title: 'One model-swap interface',
    description: (
      <>
        <code>INFERENCE_BASE_URL</code> + <code>MODEL_NAME</code> are the only
        knobs that change between a local small model, a fine-tuned 7B, or a
        remote endpoint. Nothing downstream knows which model is serving.
      </>
    ),
  },
];

function Feature({icon, title, description}) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <span className={styles.featureIcon} role="img" aria-label={title}>
          {icon}
        </span>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures() {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
