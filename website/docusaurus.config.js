// @ts-check
// `@type` JSDoc annotations allow editor autocompletion and type checking
// (when paired with `@ts-check`).
// See: https://docusaurus.io/docs/api/docusaurus-config

import {themes as prismThemes} from 'prism-react-renderer';

// This runs in Node.js - Don't use client-side code here (browser APIs, JSX...)

/** @type {import('@docusaurus/types').Config} */
const config = {
  title: 'Conversion Coach',
  tagline:
    'A funnel-simulation substrate with a staged, inspectable coach — Insurance AI track (UNIQA).',
  favicon: 'img/favicon.ico',

  // Future flags, see https://docusaurus.io/docs/api/docusaurus-config#future
  future: {
    v4: true, // Improve compatibility with the upcoming Docusaurus v4
  },

  // --- GitHub Pages deployment -------------------------------------------
  // Published at https://ruslan-basyrov.github.io/hackathon/
  url: 'https://ruslan-basyrov.github.io',
  baseUrl: '/hackathon/',
  organizationName: 'ruslan-basyrov', // GitHub org/user.
  projectName: 'hackathon', // Repo name.
  trailingSlash: false,

  onBrokenLinks: 'throw',

  i18n: {
    defaultLocale: 'en',
    locales: ['en'],
  },

  // Mermaid support (BUILD_SPEC ships an architecture diagram in mermaid).
  markdown: {
    mermaid: true,
    hooks: {
      onBrokenMarkdownLinks: 'warn',
    },
  },
  themes: ['@docusaurus/theme-mermaid'],

  presets: [
    [
      'classic',
      /** @type {import('@docusaurus/preset-classic').Options} */
      ({
        docs: {
          sidebarPath: './sidebars.js',
          editUrl:
            'https://github.com/ruslan-basyrov/hackathon/tree/main/website/',
        },
        blog: false, // Project docs, not a blog.
        theme: {
          customCss: './src/css/custom.css',
        },
      }),
    ],
  ],

  themeConfig:
    /** @type {import('@docusaurus/preset-classic').ThemeConfig} */
    ({
      image: 'img/docusaurus-social-card.jpg',
      colorMode: {
        respectPrefersColorScheme: true,
      },
      navbar: {
        title: 'Conversion Coach',
        logo: {
          alt: 'Conversion Coach',
          src: 'img/logo.svg',
        },
        items: [
          {
            type: 'docSidebar',
            sidebarId: 'docsSidebar',
            position: 'left',
            label: 'Docs',
          },
          {
            href: 'https://github.com/ruslan-basyrov/hackathon',
            label: 'GitHub',
            position: 'right',
          },
        ],
      },
      footer: {
        style: 'dark',
        links: [
          {
            title: 'Docs',
            items: [
              {label: 'Introduction', to: '/docs/intro'},
              {label: 'Architecture', to: '/docs/architecture'},
              {label: 'Build phases', to: '/docs/phases'},
              {label: 'Running locally', to: '/docs/running-locally'},
            ],
          },
          {
            title: 'Hackathon',
            items: [
              {
                label: 'Zero One Hack_01',
                href: 'https://docs.zero-one.lumos-consulting.at/',
              },
              {
                label: 'AI Factory Austria',
                href: 'https://aifactory.at',
              },
            ],
          },
          {
            title: 'More',
            items: [
              {
                label: 'GitHub',
                href: 'https://github.com/ruslan-basyrov/hackathon',
              },
            ],
          },
        ],
        copyright: `Copyright © ${new Date().getFullYear()} Conversion Coach. Built with Docusaurus.`,
      },
      prism: {
        theme: prismThemes.github,
        darkTheme: prismThemes.dracula,
        additionalLanguages: ['python', 'bash', 'yaml', 'docker'],
      },
    }),
};

export default config;
