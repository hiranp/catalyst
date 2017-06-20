import os
from datetime import datetime

import numpy as np
import pandas as pd
from pandas_datareader.data import DataReader
import requests

from catalyst.utils.calendars import register_calendar_alias
from catalyst.utils.cli import maybe_show_progress
from .core import register


def _cachpath(symbol, type_):
    return '-'.join((symbol.replace(os.path.sep, '_'), type_))


def poloniex_cryptoassets(symbols, start=None, end=None):
    """Create a data bundle ingest function from a set of symbols loaded from
    poloniex

    Parameters
    ----------
    symbols : iterable[str]
        The ticker symbols to load data for.
    start : datetime, optional
        The start date to query for. By default this pulls the full history
        for the calendar.
    end : datetime, optional
        The end date to query for. By default this pulls the full history
        for the calendar.

    Returns
    -------
    ingest : callable
        The bundle ingest function for the given set of symbols.

    Examples
    --------
    This code should be added to ~/.catalyst/extension.py

    .. code-block:: python

       from catalyst.data.bundles import poloniex_cryptoassets, register

       symbols = (
           'USDT_BTC',
           'USDT_ETH',
           'USDT_LTC',
       )
       register('my_bundle', poloniex_cryptoassets(symbols))

    Notes
    -----
    The sids for each symbol will be the index into the symbols sequence.
    """
    # strict this in memory so that we can reiterate over it
    symbols = tuple(symbols)

    def ingest(environ,
               asset_db_writer,
               minute_bar_writer,  # unused
               daily_bar_writer,
               adjustment_writer,
               calendar,
               start_session,
               end_session,
               cache,
               show_progress,
               output_dir,
               # pass these as defaults to make them 'nonlocal' in py2
               start=start,
               end=end):
        if start is None:
            start = start_session
        if end is None:
            end = None

        metadata = pd.DataFrame(np.empty(len(symbols), dtype=[
            ('start_date', 'datetime64[ns]'),
            ('end_date', 'datetime64[ns]'),
            ('auto_close_date', 'datetime64[ns]'),
            ('symbol', 'object'),
        ]))

        def _pricing_iter():
            sid = 0

            for symbol in symbols:
                #def to_dataframe(self, start, end, currencyPair=None):
                csv_fn = '/var/tmp/' + 'crypto_prices-' + symbol + '.csv'  # TODO: DIR as parameter
                #last_date = self._get_start_date(csv_fn)
                #if last_date + 300 < end or not os.path.exists(csv_fn):
                    # get latest data
                    #self.append_data_single_pair(currencyPair)

                # CSV holds the latest snapshot
                df = pd.read_csv(csv_fn,  names=['date', 'open', 'high', 'low', 'close', 'volume'])
                df['date']=pd.to_datetime(df['date'], utc=True, unit='s')
                df.set_index('date', inplace=True)

                df = df.resample('D').mean()

                # ToDo: we assume that the source is always up to date and complete, otherwise fetch
                if(pd.to_datetime(start).tz_convert(None) < df.index[0]): df_start = df.index[0]
                else:                                                     df_start = pd.to_datetime(start).tz_convert(None)
                if(pd.to_datetime(end).tz_convert(None) >  df.index[-1]): df_end   = df.index[-1]
                else:                                                     df_end   = pd.to_datetime(end).tz_convert(None)

                df = df.loc[ df_start : df_end ]

                # the start date is the date of the first trade and
                # the end date is the date of the last trade
                start_date = df.index[0]
                end_date = df.index[-1]
                # The auto_close date is the day after the last trade.
                ac_date = end_date + pd.Timedelta(days=1)
                metadata.iloc[sid] = start_date, end_date, ac_date, symbol

                yield sid, df
                sid += 1

            '''
            with maybe_show_progress(
                    symbols,
                    show_progress,
                    label='Downloading Yahoo pricing data: ') as it, \
                    requests.Session() as session:
                for symbol in it:
                    path = _cachpath(symbol, 'ohlcv')
                    try:
                        df = cache[path]
                    except KeyError:
                        df = cache[path] = DataReader(
                            symbol,
                            'yahoo',
                            start,
                            end,
                            session=session,
                        ).sort_index()

                    # the start date is the date of the first trade and
                    # the end date is the date of the last trade
                    start_date = df.index[0]
                    end_date = df.index[-1]
                    # The auto_close date is the day after the last trade.
                    ac_date = end_date + pd.Timedelta(days=1)
                    metadata.iloc[sid] = start_date, end_date, ac_date, symbol

                    df.rename(
                        columns={
                            'Open': 'open',
                            'High': 'high',
                            'Low': 'low',
                            'Close': 'close',
                            'Volume': 'volume',
                        },
                        inplace=True,
                    )
                    yield sid, df
                    sid += 1
        '''
        daily_bar_writer.write(_pricing_iter(), show_progress=show_progress)

        symbol_map = pd.Series(metadata.symbol.index, metadata.symbol)

        # Hardcode the exchange to "POLONIEX" for all assets and (elsewhere)
        # register "YAHOO" to resolve to the OPEN calendar, because these are
        # all cryptoassets and thus use the OPEN calendar.
        metadata['exchange'] = 'POLO'
        asset_db_writer.write(equities=metadata)

    return ingest


# bundle used when creating test data
register(
    '.test-poloniex',
    poloniex_cryptoassets(
        (
            'USDT_BTC',
            'USDT_ETH',
            'USDT_LTC',
        ),
        pd.Timestamp('2010-01-01', tz='utc'),
        pd.Timestamp('2015-01-01', tz='utc'),
    ),
    calendar_name='OPEN',
    minutes_per_day=1440,
)
