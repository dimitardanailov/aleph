import React from 'react';
import { connect } from 'react-redux';
import { compose } from 'redux';
import { withRouter } from 'react-router';

import { MenuItem } from '@blueprintjs/core/lib/esm/components/menu/menuItem';
import { Button } from '@blueprintjs/core/lib/esm/components/button/buttons';
import {
  ControlGroup,
} from '@blueprintjs/core';
import { Select } from '@blueprintjs/select';

import { Suggest } from 'src/components/common/Suggest';
import SearchAlert from 'src/components/SearchAlert/SearchAlert';
import Query from 'src/app/Query';
import { selectQueryLogsLimited, selectSession } from 'src/selectors';
import { deleteQueryLog, fetchQueryLogs } from 'src/actions/queryLogsActions';
import { defineMessages, FormattedMessage, injectIntl } from 'react-intl';

import './SearchBox.scss';

const ICON_VIRTUAL_SUGGEST = 'edit';
const ICON_EXISTING_SUGGEST = undefined;

const messages = defineMessages({
  placeholder: {
    id: 'search.placeholder',
    defaultMessage: 'Search in {label}',
  },
});

class SearchBox extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      currScope: props.searchScopes[props.searchScopes.length - 1],
    };

    this.changeSearchScope = this.changeSearchScope.bind(this);
    this.onSearchSubmitClick = this.onSearchSubmitClick.bind(this);
  }

  componentDidMount() {
    const {
      queryLogs, session, query,
    } = this.props;
    if (session.loggedIn && !queryLogs.isLoading && queryLogs.shouldLoad) {
      this.props.fetchQueryLogs({ query, next: queryLogs.next });
    }
  }

  componentWillReceiveProps(nextProps) {
    const { searchScopes } = this.props;

    if (searchScopes !== nextProps.searchScopes) {
      this.setState({
        currScope: nextProps.searchScopes[nextProps.searchScopes.length - 1],
      });
    }
  }

  onChange = newSearchValue => this.props.updateSearchValue(newSearchValue);

  onItemSelect = ({ query }) => {
    this.props.updateSearchValue(query);
    this.props.doSearch(query, this.state.currScope);
  };

  onSearchSubmitClick() {
    const { searchValue, doSearch } = this.props;
    console.log('submitting', searchValue);
    doSearch(searchValue, this.state.currScope);
  }

  deleteQueryLog = queryLogItem => (event) => {
    event.stopPropagation();
    this.props.deleteQueryLog(queryLogItem);
  };

  RemoveQueryLog = ({ queryItem }) => (
    <Button
      className="querylog-remove"
      minimal
      small
      onClick={this.deleteQueryLog(queryItem)}
    >
      <FormattedMessage
        id="queryLogs.query.delete"
        defaultMessage="Remove"
      />
    </Button>
  )

  renderScopeItem = (scope, { index }) => (
    <MenuItem
      key={index}
      onClick={() => this.changeSearchScope(scope)}
      text={scope.listItem}
    />
  )

  itemRenderer = (queryItem, { handleClick, modifiers }) => {
    const icon = queryItem.isVirtual ? ICON_VIRTUAL_SUGGEST : ICON_EXISTING_SUGGEST;
    const props = {
      active: modifiers.active,
      className: 'navbar-search-item',
      key: queryItem.query,
      onClick: handleClick,
      text: queryItem.query,
      labelElement: <this.RemoveQueryLog queryItem={queryItem} />,
      icon,
    };
    return <MenuItem {...props} />;
  };

  itemListPredicate = (query, queryList) => (
    query ? [{ query, isVirtual: true }] : [{ query: '' }, ...queryList]
  )

  changeSearchScope(newScope) {
    this.setState({ currScope: newScope });
  }

  render() {
    const {
      props: { searchValue, searchScopes, intl },
      state: { currScope },
      itemRenderer, onChange,
      itemListPredicate,
      onItemSelect,
    } = this;

    const inputProps = {
      type: 'text',
      className: 'bp3-fill',
      leftIcon: 'search',
      placeholder: intl.formatMessage(messages.placeholder, { label: currScope.label }),
      rightElement: <SearchAlert queryText={searchValue} />,
      value: searchValue,
      id: 'search-box',
    };

    const popoverProps = {
      popoverClassName: 'search-popover',
      targetTagName: 'div',
      fill: true,
      modifiers: {
        arrow: { enabled: false },
      },
    };

    if (!this.props.session.loggedIn || searchValue) {
      Object.assign(popoverProps, { isOpen: false });
    }

    return (
      <ControlGroup vertical={false} fill>
        {searchScopes.length > 1 && (
          <Select
            filterable={false}
            items={searchScopes}
            itemRenderer={this.renderScopeItem}
            popoverProps={{ minimal: true, className: 'SearchBox__scoped-input__popover' }}
          >
            <Button
              className="SearchBox__scoped-input__scope-button"
              text={currScope.listItem}
              rightIcon="caret-down"
            />
          </Select>
        )}
        <Suggest
          inputProps={inputProps}
          popoverProps={popoverProps}
          searchScopes={searchScopes}
          items={this.props.queryLogs.results}
          itemRenderer={itemRenderer}
          inputValueRenderer={({ text }) => text}
          onQueryChange={onChange}
          query={searchValue}
          itemListPredicate={itemListPredicate}
          className="navbar-search-input"
          onItemSelect={onItemSelect}
          resetOnQuery
        />
        <Button
          className="SearchBox__submit bp3-fixed"
          text="Search"
          onClick={this.onSearchSubmitClick}
          minimal
        />
        <Button
          className="SearchBox__search-tips bp3-fixed"
          text="Tips"
          icon="lightbulb"
          rightIcon="caret-down"
          minimal
        />
      </ControlGroup>
    );
  }
}

const mapStateToProps = state => ({
  session: selectSession(state),
  queryLogs: selectQueryLogsLimited(state),
  query: Query.fromLocation('querylog', window.location, {}, 'querylog')
    .limit(20),
});

const mapDispatchToProps = ({
  fetchQueryLogs,
  deleteQueryLog,
});


export default compose(
  withRouter,
  connect(mapStateToProps, mapDispatchToProps),
  injectIntl,
)(SearchBox);
