from setuptools import setup


setup(
    name='central-linter-ci',
    use_scm_version=True,
    packages=['lint'],
    include_package_data=True,
    scripts=[
        'script/jira_ticket_linter.py',
        'script/messages.py',
        'script/copy_linter_config.py',
    ],
    install_requires=[
        'colorama',
        'pre-commit',
        'requests',
    ],
)
